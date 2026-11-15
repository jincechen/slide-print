# Changelog

All notable changes to SlidePrint are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

SlidePrint now also runs on macOS, with the same window and features as on Windows.

### Added

- macOS app for Macs with Apple silicon or Intel processors (macOS 11 or later).
- On a Mac, PDFs and folders can also be dropped onto SlidePrint in the Dock or the Finder, or opened with **Open With → SlidePrint**.
- SHA-256 checksums of the downloads (`SHA256SUMS.txt`).

### Changed

- Download file names include the version, system and processor, for example `SlidePrint-1.1.0-windows-x86_64.exe`.

## [1.0.0] - 2026-10-06

First release: the Windows app.

### Added

- Drop PDFs or a folder onto the window, or onto `SlidePrint.exe`; each result is saved next to the original as `<name>_print.pdf`.
- A page is removed only when everything on it also appears on the next page; if a click replaces content rather than adding to it, both pages are kept.
- Kept pages are copied as they are, so text stays selectable and bookmarks, links and image quality are preserved.

[Unreleased]: https://github.com/jincechen/slide-print/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/jincechen/slide-print/releases/tag/v1.0.0
