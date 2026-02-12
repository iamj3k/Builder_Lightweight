# Builder Lightweight Desktop Launcher

This repository now includes a desktop launcher that embeds a local calculator engine and exposes:

- **Login (EVE SSO)** button
- **Refresh data** button
- **Export CSV** button

The launcher reads a **fixed app config file** (`app_config.json`) that is bundled into the executable.

## Run locally

```bash
python -m src.launcher
```

## Build Windows executable (PyInstaller)

```powershell
pip install -r requirements.txt
scripts\build_pyinstaller_windows.bat
```

Expected output:

- `dist\BuilderLightweightLauncher.exe`

## Build Windows executable (Nuitka)

```powershell
pip install -r requirements.txt
scripts\build_nuitka_windows.bat
```

Expected output:

- `BuilderLightweightLauncher.exe`

## Clean VM verification checklist

1. Start a clean Windows VM with no Python installed.
2. Copy only `BuilderLightweightLauncher.exe` to the VM.
3. Launch executable.
4. Confirm UI opens with all three buttons.
5. Click **Refresh data** and verify status updates with totals.
6. Click **Export CSV** and verify a CSV file is saved.
7. Configure `esi.client_id` in bundled config before full EVE SSO login verification.

## Notes

- `app_config.json` carries default blueprints, ME/TE, structure/system assumptions, tax, and target locations.
- You can edit those defaults before building to ship a different fixed bundle.
