# Thumbnail Maker

A small cross-platform (Windows / macOS / Linux) desktop app that batch-generates
1280×720 YouTube thumbnails in a clean editorial-panel style: a solid color panel
holding a large all-caps serif title and a letter-spaced subtitle, with your photo
filling the rest of the frame.

![example](assets/example.jpg)

## What it does

- **Simple GUI** — pick an **input folder** of photos and an **output folder**.
- **Batch** — every image in the input folder becomes one thumbnail.
- **Title per image** comes from the file name: `feet-first.jpg` → **FEET FIRST**
  (up to two auto-balanced lines).
- **Set once for the whole batch**: subtitle text, panel color, panel side
  (left/right), and uppercase on/off.
- **Live preview** of the first image so you can dial in the look before rendering.

Output files are written as `<name>_thumb.jpg` in the output folder.

## Install & run

Requires Python 3.10+ (tkinter ships with the official python.org installers on
Windows and macOS).

```bash
pip install -r requirements.txt
python app.py
```

## Naming your photos

The title is derived from the file name — hyphens, underscores and dots become
spaces. So name the input photos after the video title:

| File name                     | Title on thumbnail   |
| ----------------------------- | -------------------- |
| `feet-first.jpg`              | FEET FIRST           |
| `rebuild_your_foundation.png` | REBUILD YOUR FOUNDATION |
| `hip openers.jpg`             | HIP OPENERS          |

The subtitle (e.g. `20 MINUTE PRACTICE`) is the same for every thumbnail in a
run — set it in the app.

## Scripting (no GUI)

`render.py` is a standalone engine you can call directly:

```python
import render
style = render.Style(panel_color="#72204E", subtitle="20 MINUTE PRACTICE")
render.batch_render("photos/", "thumbnails/", style)
```

## Packaging as a desktop app

The app can be bundled into a standalone double-clickable application with
[PyInstaller](https://pyinstaller.org). **PyInstaller does not cross-compile** —
build the Windows `.exe` on a Windows machine and the macOS `.app` on a Mac. The
same [`ThumbnailMaker.spec`](ThumbnailMaker.spec) is used on both; it bundles the
font and embeds the version number.

**Windows** (produces `dist\ThumbnailMaker.exe`):

```powershell
./build_windows.ps1
```

**macOS** (produces `dist/Thumbnail Maker.app`):

```bash
./build_macos.sh
```

The version comes from [`version.py`](version.py) (single source of truth). It is
shown in the window title and footer of the GUI, and embedded in the build — the
Windows `.exe` file-properties version resource and the macOS `Info.plist`
(`CFBundleShortVersionString`). Bump `__version__` there and rebuild.

### Distribution notes

- **macOS Gatekeeper:** an unsigned `.app` shows "unidentified developer" on first
  launch. Users right-click → **Open** once, or you run
  `xattr -dr com.apple.quarantine "dist/Thumbnail Maker.app"`. For frictionless
  distribution you'd need an Apple Developer ID to sign + notarize.
- **Windows SmartScreen** may warn on an unsigned `.exe`; a code-signing
  certificate removes it.
- **Icons** are optional — drop `assets/icon.ico` (Windows) / `assets/icon.icns`
  (macOS) and set the `icon=` fields in the spec.

## Font & license

Titles use **Playfair Display** (SIL Open Font License), bundled in `fonts/`
(`fonts/OFL.txt`) so output looks identical on every OS. Application code is
yours to use freely.
