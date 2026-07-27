# PyInstaller spec — build with:  pyinstaller ThumbnailMaker.spec
#
# Cross-OS note: PyInstaller does NOT cross-compile. Run this spec ON Windows to
# get a .exe, and ON macOS to get a .app. The same file works on both.

import sys

block_cipher = None

# Single source of truth for the version.
_ns = {}
with open("version.py", "r", encoding="utf-8") as _f:
    exec(_f.read(), _ns)
VERSION = _ns["__version__"]
_parts = [int(p) for p in VERSION.split(".")]
while len(_parts) < 4:
    _parts.append(0)
VERSION_TUPLE = tuple(_parts[:4])

# Bundle the fonts/ folder (the app crashes without the .ttf).
datas = [("fonts", "fonts")]

# --- Windows: build a version-info resource so the .exe has a real version ---
win_version = None
if sys.platform == "win32":
    from PyInstaller.utils.win32.versioninfo import (
        VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable,
        StringStruct, VarFileInfo, VarStruct,
    )
    win_version = VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=VERSION_TUPLE, prodvers=VERSION_TUPLE,
            mask=0x3F, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,
        ),
        kids=[
            StringFileInfo([StringTable("040904B0", [
                StringStruct("CompanyName", "Thumbnail Maker"),
                StringStruct("FileDescription", "Thumbnail Maker"),
                StringStruct("FileVersion", VERSION),
                StringStruct("ProductName", "Thumbnail Maker"),
                StringStruct("ProductVersion", VERSION),
            ])]),
            VarFileInfo([VarStruct("Translation", [1033, 1200])]),
        ],
    )

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ThumbnailMaker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,          # windowed app, no terminal window
    disable_windowed_traceback=False,
    icon=None,              # set to "assets/icon.ico" (Win) / "assets/icon.icns" (mac) if you add one
    version=win_version,    # embeds version resource on Windows (None elsewhere)
)

# On macOS, wrap the executable in a proper .app bundle.
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="Thumbnail Maker.app",
        icon=None,          # "assets/icon.icns" if you add one
        bundle_identifier="com.thumbnailmaker.app",
        version=VERSION,
        info_plist={
            "CFBundleName": "Thumbnail Maker",
            "CFBundleDisplayName": "Thumbnail Maker",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
        },
    )
