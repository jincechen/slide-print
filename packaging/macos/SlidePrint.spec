# PyInstaller spec for SlidePrint.app, the macOS app (the Windows .exe is built from the
# command line, in packaging/windows/build.bat). Used by build.sh and the workflow, from
# the repository's top folder:
#
#   ICONSET=layers python -m PyInstaller --noconfirm packaging/macos/SlidePrint.spec
#
# A spec rather than command-line options because the app's Info.plist needs keys that
# PyInstaller has no options for (accepting PDFs and folders dropped onto the app, etc.).
#
# SPDX-License-Identifier: AGPL-3.0-or-later
import os, re

ROOT = os.path.abspath(os.path.join(SPECPATH, '..', '..'))
ICONS = os.path.join(ROOT, 'icons', os.environ.get('ICONSET', 'layers'))     # icon set to ship: a folder in icons/
with open(os.path.join(ROOT, 'slideprint', '__init__.py'), encoding='utf-8') as f:
    VERSION = re.search(r"^__version__ = '(.+)'", f.read(), re.M).group(1)
SAVE_NEXT = 'SlidePrint saves the print version of a PDF next to the original.'

a = Analysis(
    [os.path.join(ROOT, 'slideprint', '__main__.py')],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, 'LICENSE'), '.'), (os.path.join(ROOT, 'THIRD_PARTY_NOTICES.txt'), '.'),
           (os.path.join(ROOT, 'slideprint', 'ui.html'), '.'), (os.path.join(ICONS, 'logo.png'), '.')],
    excludes=['pyi_splash'],                            # no start-up splash on macOS
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='SlidePrint', console=False)
coll = COLLECT(exe, a.binaries, a.datas, name='SlidePrint')
app = BUNDLE(
    coll,
    name='SlidePrint.app',
    icon=os.path.join(ICONS, 'icon.icns'),
    bundle_identifier='io.github.jincechen.slideprint',
    version=VERSION,
    info_plist={
        'CFBundleVersion': VERSION,
        'NSHumanReadableCopyright': 'Copyright © 2026 Jince Chen. GNU AGPL v3.0 or later.',
        'LSApplicationCategoryType': 'public.app-category.productivity',
        'LSMinimumSystemVersion': '11.0',
        'NSRequiresAquaSystemAppearance': False,            # follow Dark Mode
        # PDFs and folders dropped onto the app in the Finder or the Dock (the folders' PDFs
        # are processed), and PDFs opened with it ("Open With"; never the default app)
        'CFBundleDocumentTypes': [
            {'CFBundleTypeName': 'PDF document', 'CFBundleTypeRole': 'Viewer',
             'LSItemContentTypes': ['com.adobe.pdf'], 'LSHandlerRank': 'Alternate'},
            {'CFBundleTypeName': 'Folder', 'CFBundleTypeRole': 'Viewer',
             'LSItemContentTypes': ['public.folder'], 'LSHandlerRank': 'None'},
        ],
        # shown when macOS first asks to let SlidePrint save in these places
        'NSDesktopFolderUsageDescription': SAVE_NEXT,
        'NSDocumentsFolderUsageDescription': SAVE_NEXT,
        'NSDownloadsFolderUsageDescription': SAVE_NEXT,
        'NSRemovableVolumesUsageDescription': SAVE_NEXT,
        'NSNetworkVolumesUsageDescription': SAVE_NEXT,
    },
)
