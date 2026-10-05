# SlidePrint

Slide PDFs often turn every click into a separate page. SlidePrint removes those intermediate build-up pages and keeps the complete version of each slide, making the PDF much easier to print or read.

Your original file is never changed.

## Using it

1. Download **SlidePrint.exe** from the [latest release](https://github.com/jincechen/slide-print/releases/latest). No installation is needed.
2. Open it and drop in one or more PDFs. You can also drop a folder to process every PDF inside it, or drop files directly onto `SlidePrint.exe`.
3. Each result is saved next to the original as `<name>_print.pdf`.

If something goes wrong, click **Copy details** next to the file and include that text when you [open an issue](https://github.com/jincechen/slide-print/issues).

SlidePrint requires Microsoft Edge WebView2, which is already included with Windows 11 and normally comes with Edge on Windows 10.

The first time you run SlidePrint, Windows may show *“Windows protected your PC”* because the app is unsigned. Click **More info → Run anyway**.

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

Install the dependencies:

```bash
pip install -r requirements.txt
```

Run the app:

```bash
python slideprint_gui.py
```

The core PDF processor can also be used directly:

```bash
python dedup_slides.py talk.pdf
```

Some useful options:

```bash
python dedup_slides.py talk.pdf -o out.pdf
python dedup_slides.py talk.pdf --dry-run
python test_dedup_slides.py
```

The main files are:

- `dedup_slides.py` — finds build-up pages and writes the print version
- `slideprint_gui.py` — Python side of the Windows app
- `ui.html` — app interface
- `test_dedup_slides.py` — basic tests
- `build.bat` — builds `SlidePrint.exe`
- `.github/workflows/build.yml` — tests, builds, and publishes releases

## Building

Run:

```bash
build.bat
```

This produces:

```text
dist\SlidePrint.exe
```

The GitHub Actions workflow also builds the app automatically and publishes a release when you push a version tag such as `v1.0.0`.

## Licence

© 2026 Jince Chen

SlidePrint is free software under the GNU Affero General Public License v3.0 or later. See [`LICENSE`](LICENSE) for details.

It uses [PyMuPDF](https://github.com/pymupdf/PyMuPDF) and [pywebview](https://github.com/r0x0r/pywebview). Third-party licences are listed in [`THIRD_PARTY_NOTICES.txt`](THIRD_PARTY_NOTICES.txt).
