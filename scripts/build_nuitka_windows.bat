@echo off
setlocal
python -m nuitka --onefile --standalone --windows-console-mode=disable --include-data-files=app_config.json=app_config.json --output-filename=BuilderLightweightLauncher.exe src\launcher.py
endlocal
