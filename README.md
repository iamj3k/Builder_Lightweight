# Builder Lightweight Desktop Launcher

This repository now includes a desktop launcher that embeds a local calculator engine and exposes:

- **Connected / Reconnect** button
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
4. Confirm UI opens with **Connected/Reconnect**, **Refresh data**, and **Export CSV**.
5. Click **Refresh data** and verify status updates with totals.
6. Click **Export CSV** and verify a CSV file is saved.
7. Configure `esi.client_id` in bundled config before full EVE SSO login verification.


## ESI hub mapping rules (`*_on_market`, `*_stock`)

Hub columns in the CSV are populated from ESI using fixed location IDs:

- `*_on_market` = sum of ESI **order** `volume_remain` for rows whose `location_id` is mapped to that hub.
- `*_stock` = sum of ESI **asset** `quantity` for rows whose `location_id` is mapped to that hub.
- For hubs with multiple IDs, values are aggregated by summing across **all** mapped IDs.

Configured hub -> location IDs:

- **Jita**: `60003760` (Jita IV - Moon 4 - Caldari Navy Assembly Plant), `1022734985679` (Perimeter - Tranquility Trading Tower)
- **Amarr**: `60008494` (Amarr VIII (Oris) - Emperor Family Academy)
- **Dodixie**: `60011866` (Dodixie IX - Moon 20 - Federation Navy Assembly Plant)
- **O-PNSN**: `1036927076065`
- **C-N4OD**: `1037131880317`

These mappings are defined in `src/configuration.py::MARKET_HUB_LOCATION_IDS` and consumed by `EsiCharacterStateAdapter.get_hub_state_records(...)`.


## OAuth behavior

- The app opens the system browser for EVE SSO login using OAuth2 PKCE.
- The callback is captured from the configured localhost redirect URI.
- Refresh tokens are encrypted with Windows DPAPI before being stored on disk.
- The launcher auto-refreshes access tokens before data refreshes.
- The UI intentionally only exposes **Connected** or **Reconnect** and hides token/expiry details.

## Notes

- `app_config.json` carries default blueprints, ME/TE, structure/system assumptions, tax, and target locations.
- You can edit those defaults before building to ship a different fixed bundle.
