"""SlidePrint: the window around dedup for people who do not use the command
line (python -m slideprint). Built into SlidePrint.exe on Windows and
SlidePrint.app on macOS (see README.md).

The window is ui.html shown in the system's web view (Edge WebView2, part of
Windows 10/11; WKWebView, part of macOS) via pywebview; this file is its
Python side. Files can be chosen, dropped onto the window, or dropped onto the
app (SlidePrint.exe; SlidePrint.app in the Finder or the Dock, or "Open With");
several at once, and folders (their PDFs) too. Each print version is saved
next to its original as <name>_print.pdf, or wherever the user picks if that
folder cannot be written.

Copyright (C) 2026 Jince Chen
SPDX-License-Identifier: AGPL-3.0-or-later
"""
import base64, ctypes, json, os, platform, subprocess, sys, tempfile, threading, traceback, webbrowser

if sys.stdout is None:                      # windowed .exe / .app: no console to print to
    sys.stdout = sys.stderr = open(os.devnull, 'w')

import webview
from webview.dom import DOMEventHandler

from slideprint import __version__ as VERSION

MAC = sys.platform == 'darwin'
APP = 'SlidePrint'
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                    # the repository, when run from source
SOURCE_URL = 'https://github.com/jincechen/slide-print'      # AGPL: where users get the source
WEBVIEW2_URL = 'https://developer.microsoft.com/microsoft-edge/webview2/'
NO_PDFS = 'No PDF files found.'

_lib = None
_lib_lock = threading.Lock()


def lib():
    """(pymupdf, dedup), imported on first use so that the window opens sooner."""
    global _lib
    with _lib_lock:
        if _lib is None:
            import pymupdf
            from slideprint import dedup
            _lib = pymupdf, dedup
    return _lib


class UserError(Exception):
    """A problem the user can fix; shown as is. retry: offer "Try again"; pdf=False: not a PDF at all."""
    def __init__(self, msg, retry=False, pdf=True):
        super().__init__(msg)
        self.retry, self.pdf = retry, pdf


def resource(name, folder=HERE):
    """A file shipped with the app: inside the .exe / .app when frozen by PyInstaller, else in
    folder (this package, or ROOT)."""
    return os.path.join(getattr(sys, '_MEIPASS', folder), name)


def icon_file(name):
    """icon.ico / icon.icns / logo.png of the icon set: the one bundled into the app (ICONSET in
    build.bat / build.sh), or, run from source, icons/<SLIDEPRINT_ICONSET or layers>/."""
    return resource(name, os.path.join(ROOT, 'icons', os.environ.get('SLIDEPRINT_ICONSET', 'layers')))


def writable(path):
    """Can we (over)write path? Leaves no trace if it did not exist."""
    existed = os.path.exists(path)
    try:
        with open(path, 'ab'):
            pass
    except OSError:
        return False
    if not existed:
        os.remove(path)
    return True


def expand(paths):
    """Files as given; folders become the PDFs directly inside them."""
    out = []
    for p in paths:
        p = os.path.normpath(p)
        if os.path.isdir(p):
            out += sorted(os.path.join(p, f) for f in os.listdir(p)
                          if f.lower().endswith('.pdf') and not f.lower().endswith('_print.pdf'))
        elif os.path.isfile(p):
            out.append(p)
    return out


def os_version():
    if MAC:
        return f'macOS {platform.mac_ver()[0]} {platform.machine()}'
    return f'Windows {platform.version()}'


def error_report(path, exc):
    """Short text the user can paste into a message to report a problem."""
    frames = traceback.extract_tb(exc.__traceback__)[-3:]
    pymupdf, _ = lib()
    return '\n'.join([f'{APP} {VERSION} | PyMuPDF {pymupdf.VersionBind} | {os_version()}',
                      f'File: {os.path.basename(path)}',
                      f'Error: {type(exc).__name__}: {exc}']
                     + [f'  at {os.path.basename(f.filename)}:{f.lineno} in {f.name}' for f in frames])


def open_path(path):
    """Open a file in its default app."""
    if MAC:
        subprocess.run(['open', os.path.abspath(path)])
    else:
        os.startfile(path)


def reveal(path):
    """Show a file, selected, in Explorer / the Finder."""
    if MAC:
        subprocess.run(['open', '-R', os.path.abspath(path)])
    else:
        subprocess.Popen(['explorer', '/select,', os.path.normpath(path)])


def copy_to_clipboard(text):
    """System clipboard, with no extra packages: the Win32 API on Windows, NSPasteboard
    (PyObjC, which pywebview uses on macOS) on macOS."""
    if MAC:
        from AppKit import NSPasteboard, NSPasteboardTypeString
        board = NSPasteboard.generalPasteboard()
        board.clearContents()
        return bool(board.setString_forType_(text, NSPasteboardTypeString))
    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    k32.GlobalAlloc.restype = k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    u32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    data = text.encode('utf-16-le') + b'\0\0'
    if not u32.OpenClipboard(None):
        return False
    try:
        u32.EmptyClipboard()
        h = k32.GlobalAlloc(0x0002, len(data))              # GMEM_MOVEABLE
        ctypes.memmove(k32.GlobalLock(h), data, len(data))
        k32.GlobalUnlock(h)
        return bool(u32.SetClipboardData(13, h))            # CF_UNICODETEXT
    finally:
        u32.CloseClipboard()


class Api:
    """Called from ui.html as window.pywebview.api.<name>(...)."""

    def __init__(self, files, notice=''):
        self._files = files
        self._notice = notice
        self._window = None
        self._ready = False                 # the page has called info(), so it can take more files
        self._lock = threading.Lock()

    def info(self):
        with self._lock:
            self._ready = True
            files, notice, self._files, self._notice = self._files, self._notice, [], ''
        return {'version': VERSION, 'files': files, 'notice': notice, 'mac': MAC}

    def _add_files(self, paths):
        """Files from outside the page: dropped onto the window, or onto the app on macOS. Not from
        the main (UI) thread: evaluate_js waits for it."""
        found = expand(paths)
        with self._lock:
            if not self._ready:             # page still loading: info() hands them over
                self._files += found
                if paths and not found:
                    self._notice = NO_PDFS
                return
        if found:
            self._window.evaluate_js(f'addFiles({json.dumps(found)})')
        elif paths:
            self._window.evaluate_js(f'toast({json.dumps(NO_PDFS)})')

    def choose_files(self):
        # macOS dialogs have no file-type menu, so PDFs only there
        types = ('PDF files (*.pdf)',) if MAC else ('PDF files (*.pdf)', 'All files (*.*)')
        paths = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=True, file_types=types)
        return expand(paths or [])

    def process(self, path):
        path = os.path.normpath(path)
        try:
            return self._process(path)
        except UserError as e:
            return {'state': 'error', 'text': str(e), 'retry': e.retry, 'pdf': e.pdf}
        except Exception as e:
            return {'state': 'error', 'text': 'Something went wrong. Copy the details to report it.',
                    'report': error_report(path, e), 'retry': True}

    def _process(self, path):
        if not os.path.isfile(path):
            raise UserError('File not found')
        try:
            with open(path, 'rb') as f:                     # work from memory: the file is not kept open
                data = f.read()
        except OSError:
            raise UserError('Cannot read this file. Close it in other programs, then try again.', retry=True)
        pymupdf, _ = lib()
        try:
            doc = pymupdf.open(stream=data, filetype='pdf')
        except Exception:
            raise UserError('Not a PDF file', pdf=False)
        try:
            return self._convert(doc, path)
        finally:
            doc.close()

    def _convert(self, doc, path):
        if doc.needs_pass:
            raise UserError('Password-protected. Remove the password, then try again.')
        if not doc.is_pdf or len(doc) == 0:
            raise UserError('Not a PDF file', pdf=False)
        _, ds = lib()
        n = len(doc)
        groups, _ = ds.group_pages(doc)
        if len(groups) == n:
            return {'state': 'none', 'text': f'Nothing to remove ({n} pages)'}
        out = os.path.splitext(path)[0] + '_print.pdf'
        if not writable(out):
            if os.path.exists(out):
                raise UserError(f"Can't overwrite {os.path.basename(out)}. Close it if it's open, then try again.",
                                retry=True)
            picked = self._window.create_file_dialog(webview.FileDialog.SAVE, save_filename=os.path.basename(out),
                                                     file_types=('PDF files (*.pdf)',))
            if not picked:
                raise UserError('Not saved: no folder chosen', retry=True)
            out = picked if isinstance(picked, str) else picked[0]
            if MAC and not out.lower().endswith('.pdf'):    # unlike Windows', the macOS dialog does not add it
                out += '.pdf'
        try:
            ds.write_output(doc, groups, out)
        except Exception:
            raise UserError(f'Could not save {os.path.basename(out)}. Close it if it is open, then try again.',
                            retry=True)
        return {'state': 'ok', 'text': f'{n} → {len(groups)} pages', 'out': out}

    def open_file(self, path):
        if not os.path.isfile(path):
            return False
        open_path(path)
        return True

    def show_in_folder(self, path):
        if not os.path.isfile(path):
            return False
        reveal(path)
        return True

    def copy(self, text):
        return copy_to_clipboard(text)

    def open_source(self):
        webbrowser.open(SOURCE_URL)

    def open_licences(self):
        """SlidePrint's licence and the bundled software's, as one text file."""
        parts = [f'{APP} {VERSION}, Copyright (C) 2026 Jince Chen. Source code: {SOURCE_URL}\n']
        for name in ('THIRD_PARTY_NOTICES.txt', 'LICENSE'):
            with open(resource(name, ROOT), encoding='utf-8') as f:
                parts.append(f.read())
        path = os.path.join(tempfile.gettempdir(), f'{APP} licences.txt')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(('\n\n' + '=' * 78 + '\n\n').join(parts))
        open_path(path)


def close_splash():
    """Close the "Starting..." card that SlidePrint.exe shows while it unpacks (exe only: the .app
    on macOS does not unpack, and PyInstaller has no splash there)."""
    try:
        import pyi_splash
        pyi_splash.close()
    except ImportError:
        pass


def on_shown():
    """Window is up: close the splash and load the PDF code in the background."""
    close_splash()
    threading.Thread(target=lib, daemon=True).start()


def has_webview2():
    """pywebview silently falls back to Internet Explorer, which cannot show ui.html."""
    from webview.platforms import winforms
    return winforms.renderer == 'edgechromium'


def accept_opened_files(add_files):
    """macOS hands SlidePrint.app the files dropped onto it in the Finder or the Dock, or opened
    with it, as an Apple Event to the running app (also when that starts it), not on the command
    line as Windows does: receive them on pywebview's application delegate."""
    import AppKit
    from webview.platforms import cocoa

    class SlidePrintAppDelegate(cocoa.BrowserView.AppDelegate):
        def application_openFiles_(self, app, filenames):
            paths = [str(f) for f in filenames]
            threading.Thread(target=add_files, args=(paths,), daemon=True).start()     # off the UI thread
            app.replyToOpenOrPrint_(AppKit.NSApplicationDelegateReplySuccess)

    cocoa.BrowserView.AppDelegate = SlidePrintAppDelegate


def app_icon():
    """The window icon on Windows. On macOS the .app has its own icon; only run from source does
    the Dock need one (instead of Python's)."""
    if not MAC:
        return icon_file('icon.ico')
    return None if hasattr(sys, '_MEIPASS') else icon_file('icon.icns')


def main():
    if not MAC and not has_webview2():
        close_splash()
        msg = ('SlidePrint needs Microsoft Edge WebView2, which is missing on this PC.\n\n'
               'Click OK to open the Microsoft download page. Install the "Evergreen Bootstrapper", '
               'then start SlidePrint again.')
        if ctypes.windll.user32.MessageBoxW(None, msg, APP, 0x31) == 1:          # MB_OKCANCEL | MB_ICONWARNING
            webbrowser.open(WEBVIEW2_URL)
        return
    files = expand(sys.argv[1:])                            # files dropped onto the .exe icon (macOS: below)
    api = Api(files, NO_PDFS if sys.argv[1:] and not files else '')
    with open(resource('ui.html'), encoding='utf-8') as f:
        html = f.read()
    with open(icon_file('logo.png'), 'rb') as f:
        html = html.replace('{{LOGO}}', 'data:image/png;base64,' + base64.b64encode(f.read()).decode())
    window = webview.create_window(APP, html=html, js_api=api, width=580, height=640, min_size=(460, 480),
                                   background_color='#f6f7f9')
    api._window = window

    def on_drop(e):                                         # runs on a worker thread
        paths = [f.get('pywebviewFullPath') for f in e.get('dataTransfer', {}).get('files', [])]
        api._add_files([p for p in paths if p])

    def bind():
        window.dom.document.events.drop += DOMEventHandler(on_drop, True, True)

    if MAC:
        accept_opened_files(api._add_files)
    window.events.loaded += bind
    window.events.shown += on_shown
    webview.start(icon=app_icon())


if __name__ == '__main__':
    main()
