# Build the Windows .exe.  Run on Windows:  ./build_windows.ps1
$ErrorActionPreference = "Stop"
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --clean --noconfirm ThumbnailMaker.spec
Write-Host ""
Write-Host "Built: dist\ThumbnailMaker.exe" -ForegroundColor Green
