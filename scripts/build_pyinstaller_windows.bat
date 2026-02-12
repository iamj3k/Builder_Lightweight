@echo off
setlocal
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
pyinstaller --noconfirm --onefile --windowed --name BuilderLightweightLauncher --add-data "app_config.json;." src\launcher.py
endlocal
