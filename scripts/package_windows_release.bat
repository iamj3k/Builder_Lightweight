@echo off
setlocal

if not exist dist\BuilderLightweightLauncher.exe (
  echo Missing dist\BuilderLightweightLauncher.exe
  echo Build with scripts\build_pyinstaller_windows.bat first.
  exit /b 1
)

set RELEASE_DIR=release\BuilderLightweight
if exist %RELEASE_DIR% rmdir /s /q %RELEASE_DIR%
mkdir %RELEASE_DIR%

copy dist\BuilderLightweightLauncher.exe %RELEASE_DIR%\BuilderLightweightLauncher.exe >nul
copy app_config.json %RELEASE_DIR%\app_config.json >nul
copy README.md %RELEASE_DIR%\README.md >nul

powershell -NoProfile -Command "Compress-Archive -Path '%RELEASE_DIR%\*' -DestinationPath 'release\BuilderLightweight-windows.zip' -Force"
if errorlevel 1 exit /b 1

echo Packaged release\BuilderLightweight-windows.zip
endlocal
