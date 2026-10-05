#!/usr/bin/env python3
"""SlidePrint: the window around dedup_slides for people who do not use the
command line. Built into SlidePrint.exe (see README.md).

The window is ui.html shown in the system's web view (Edge WebView2, part of
Windows 10/11) via pywebview; this file is its Python side. Files can be
chosen, dropped onto the window, or dropped onto SlidePrint.exe; several at
once, and folders (their PDFs) too. Each print version is saved next to its
original as <name>_print.pdf, or wherever the user picks if that folder
cannot be written.

Copyright (C) 2026 Jince Chen
SPDX-License-Identifier: AGPL-3.0-or-later
"""
import ctypes, json, os, platform, subprocess, sys, tempfile, threading, traceback, webbrowser

if sys.stdout is None:                      # windowed .exe: no console to print to
    sys.stdout = sys.stderr = open(os.devnull, 'w')

import webview
from webview.dom import DOMEventHandler

APP = 'SlidePrint'
VERSION = '1.0.0'
SOURCE_URL = 'https://github.com/jincechen/slide-print'      # AGPL: where users get the source
WEBVIEW2_URL = 'https://developer.microsoft.com/microsoft-edge/webview2/'
NO_PDFS = 'No PDF files found.'

_lib = None
_lib_lock = threading.Lock()


def lib():
    """(pymupdf, dedup_slides), imported on first use so that the window opens sooner."""
    global _lib
    with _lib_lock:
        if _lib is None:
            import pymupdf
            import dedup_slides
            _lib = pymupdf, dedup_slides
    return _lib


class UserError(Exception):
    """A problem the user can fix; shown as is. retry: offer "Try again"; pdf=False: not a PDF at all."""
    def __init__(self, msg, retry=False, pdf=True):
        super().__init__(msg)
        self.retry, self.pdf = retry, pdf


def resource(name):
    """A file shipped with the app (inside the .exe when frozen by PyInstaller)."""
    return os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__))), name)


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


def error_report(path, exc):
    """Short text the user can paste into a message to report a problem."""
    frames = traceback.extract_tb(exc.__traceback__)[-3:]
    pymupdf, _ = lib()
    return '\n'.join([f'{APP} {VERSION} | PyMuPDF {pymupdf.VersionBind} | Windows {platform.version()}',
                      f'File: {os.path.basename(path)}',
                      f'Error: {type(exc).__name__}: {exc}']
                     + [f'  at {os.path.basename(f.filename)}:{f.lineno} in {f.name}' for f in frames])


def copy_to_clipboard(text):
    """Windows clipboard via the Win32 API (no extra packages)."""
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

    def info(self):
        return {'version': VERSION, 'files': self._files, 'notice': self._notice}

    def choose_files(self):
        paths = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=True,
                                                file_types=('PDF files (*.pdf)', 'All files (*.*)'))
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
        try:
            ds.write_output(doc, groups, out)
        except Exception:
            raise UserError(f'Could not save {os.path.basename(out)}. Close it if it is open, then try again.',
                            retry=True)
        return {'state': 'ok', 'text': f'{n} → {len(groups)} pages', 'out': out}

    def open_file(self, path):
        if not os.path.isfile(path):
            return False
        os.startfile(path)
        return True

    def show_in_folder(self, path):
        if not os.path.isfile(path):
            return False
        subprocess.Popen(['explorer', '/select,', os.path.normpath(path)])
        return True

    def copy(self, text):
        return copy_to_clipboard(text)

    def open_source(self):
        webbrowser.open(SOURCE_URL)

    def open_licences(self):
        """SlidePrint's licence and the bundled software's, as one text file."""
        parts = [f'{APP} {VERSION}, Copyright (C) 2026 Jince Chen. Source code: {SOURCE_URL}\n']
        for name in ('THIRD_PARTY_NOTICES.txt', 'LICENSE'):
            with open(resource(name), encoding='utf-8') as f:
                parts.append(f.read())
        path = os.path.join(tempfile.gettempdir(), f'{APP} licences.txt')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(('\n\n' + '=' * 78 + '\n\n').join(parts))
        os.startfile(path)


def on_shown():
    """Window is up: load the PDF code in the background."""
    threading.Thread(target=lib, daemon=True).start()


def has_webview2():
    """pywebview silently falls back to Internet Explorer, which cannot show ui.html."""
    from webview.platforms import winforms
    return winforms.renderer == 'edgechromium'


def main():
    if not has_webview2():
        msg = ('SlidePrint needs Microsoft Edge WebView2, which is missing on this PC.\n\n'
               'Click OK to open the Microsoft download page. Install the "Evergreen Bootstrapper", '
               'then start SlidePrint again.')
        if ctypes.windll.user32.MessageBoxW(None, msg, APP, 0x31) == 1:          # MB_OKCANCEL | MB_ICONWARNING
            webbrowser.open(WEBVIEW2_URL)
        return
    files = expand(sys.argv[1:])                            # files dropped onto the .exe icon
    api = Api(files, NO_PDFS if sys.argv[1:] and not files else '')
    with open(resource('ui.html'), encoding='utf-8') as f:
        html = f.read()
    window = webview.create_window(APP, html=html, js_api=api, width=580, height=640, min_size=(460, 480),
                                   background_color='#f6f7f9')
    api._window = window

    def on_drop(e):
        paths = [f.get('pywebviewFullPath') for f in e.get('dataTransfer', {}).get('files', [])]
        paths = [p for p in paths if p]
        found = expand(paths)
        if found:
            window.evaluate_js(f'addFiles({json.dumps(found)})')
        elif paths:
            window.evaluate_js(f'toast({json.dumps(NO_PDFS)})')

    def bind():
        window.dom.document.events.drop += DOMEventHandler(on_drop, True, True)

    window.events.loaded += bind
    window.events.shown += on_shown
    webview.start()


if __name__ == '__main__':
    main()
