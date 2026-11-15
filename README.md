# SlidePrint

Slide PDFs often turn every click into a separate page. SlidePrint removes those intermediate build-up pages and keeps the complete version of each slide, making the PDF much easier to print or read.

Your original file is never changed.

<img src="docs/screenshot.png" alt="SlidePrint showing page counts and saved results for example PDFs" width="580">

## Using it

1. Download SlidePrint from the [latest release](https://github.com/jincechen/slide-print/releases/latest):
   - **Windows 10 or 11:** `SlidePrint-<version>-windows-x86_64.exe`. No installation is needed.
   - **macOS 11 or later:** `SlidePrint-<version>-macos-arm64.dmg` for Macs with Apple silicon (M1 or later), or `SlidePrint-<version>-macos-x86_64.dmg` for Intel Macs. **Apple menu → About This Mac** shows which you have. Open the `.dmg` and drag SlidePrint into Applications.
2. Open it and click **Choose files** to select one or more PDFs, or drop them into the window. Processing starts automatically.
3. Each result is saved next to the original: `talk.pdf` becomes `talk_print.pdf`. Use the **Open** or **Show in folder** (on a Mac, **Show in Finder**) icons beside the result to find it.

You can also drop a folder to process the PDFs directly inside it, or drop files directly onto the SlidePrint `.exe` file. On a Mac, drop them onto SlidePrint in the Dock or the Finder, or Control-click a PDF and choose **Open With → SlidePrint**.

### The first time

On Windows, SlidePrint may show *“Windows protected your PC”* because the app is unsigned. Click **More info → Run anyway**.

SlidePrint requires Microsoft Edge WebView2, which is already included with Windows 11 and normally comes with Edge on Windows 10.

On a Mac, macOS says that it could not verify SlidePrint, because the app is not notarised by Apple. Click **Done**, then open **System Settings → Privacy & Security**, scroll down and click **Open Anyway** next to the message about SlidePrint. On macOS 14 or earlier, you can instead Control-click SlidePrint in Applications and choose **Open**.

macOS may also ask whether SlidePrint can access files in your Desktop, Documents or Downloads folder. Allow it so that results can be saved next to the originals; otherwise SlidePrint asks where to save each one.

If something goes wrong, click **Copy details** next to the file and include that text when you [open an issue](https://github.com/jincechen/slide-print/issues).

## How it works

SlidePrint removes a page only when everything visible on it also appears on the next page. If a click replaces or removes content instead of simply adding to it, both pages are kept.

The original PDF pages are copied directly, so:

- text stays selectable;
- images stay just as sharp;
- bookmarks and links keep working;
- page content is not re-rendered or recompressed.

It works well with PDFs exported from Beamer, PowerPoint, Keynote, and similar slide software.

Password-protected PDFs need to be unlocked first.

## Running from source

To run the app from source, install Python 3.12 and open a terminal in the project folder. Install the dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run the app:

```powershell
python slideprint_gui.py
```

On a Mac, type `python3` instead of `python`.

The core PDF processor can also be used directly:

```powershell
python dedup_slides.py talk.pdf
```

Choose a different output name, or preview which pages would be kept without writing a PDF:

```powershell
python dedup_slides.py talk.pdf -o out.pdf
python dedup_slides.py talk.pdf --dry-run
```

To run the tests: `python test_dedup_slides.py`.

The main files are:

- `dedup_slides.py` — finds build-up pages and writes the print version
- `slideprint_gui.py` — Python side of the app (Windows and macOS)
- `ui.html` — app interface
- `test_dedup_slides.py` — basic tests
- `build.bat` — builds `SlidePrint.exe` on Windows
- `build.sh` and `slideprint-macos.spec` — build `SlidePrint.app` on macOS
- `.github/workflows/build.yml` — tests, builds, and publishes releases

## Building

On Windows, with Python 3.12 on your PATH, run:

```powershell
.\build.bat
```

This produces:

```text
dist\SlidePrint.exe
```

On a Mac, with Python 3.12 on your PATH as `python3.12` (from [python.org](https://www.python.org/downloads/macos/) or Homebrew), run:

```sh
./build.sh
```

This produces the app and a disk image to share it with, both for the Mac's own processor (Apple silicon or Intel):

```text
dist/SlidePrint.app
dist/SlidePrint.dmg
```

The GitHub Actions workflow also builds the apps automatically (Windows, and macOS for both Apple silicon and Intel) and publishes a release when you push a version tag such as `v1.0.0`.

## Licence

© 2026 Jince Chen

SlidePrint is free software under the GNU Affero General Public License v3.0 or later. See [`LICENSE`](LICENSE) for details.

It uses [PyMuPDF](https://github.com/pymupdf/PyMuPDF) and [pywebview](https://github.com/r0x0r/pywebview), and on macOS [PyObjC](https://github.com/ronaldoussoren/pyobjc). Third-party licences are listed in [`THIRD_PARTY_NOTICES.txt`](THIRD_PARTY_NOTICES.txt).
