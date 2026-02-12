# Builder Lightweight Desktop Launcher

This repository includes a desktop launcher that embeds a local calculator engine and exposes:

- **Connected / Reconnect** button
- **Refresh data** button
- **Export CSV** button

The launcher reads a **fixed app config file** (`app_config.json`) that is bundled into the executable.

## Milestone delivery map

### Milestone 1 — CSV schema lock + baseline exporter

Delivered:
- Fixed CSV header schema is hard-locked in `CSV_EXPORT_HEADERS`.
- Baseline CSV exporter writes all required columns in stable order.
- Regression tests validate exact schema and exporter behavior.

User-level acceptance check (**friend can run this without installing dependencies**):
1. Copy a built `BuilderLightweightLauncher.exe` to a Windows machine with no Python.
2. Run the EXE and click **Export CSV**.
3. Open the CSV and verify the first row matches the expected locked schema.

### Milestone 2 — live pricing for one hub

Delivered:
- Added live-price provider interface (`LivePriceProvider`).
- Added Jita live-price adapter from config (`ConfigJitaLivePriceProvider`).
- Export path now prefers live Jita sell price when available.

User-level acceptance check (**friend can run this without installing dependencies**):
1. Copy only the packaged release ZIP contents to a clean Windows machine.
2. Run `BuilderLightweightLauncher.exe` and click **Export CSV**.
3. Confirm `jita_sell_price` reflects configured live Jita values.

### Milestone 3 — character auth and inventory/order integration

Delivered:
- OAuth sign-in + reconnect flow is integrated with refresh.
- Character asset/open-order rows are attached after token refresh/login.
- Export now fills `quantity`, `*_stock`, and `*_on_market` from character state.

User-level acceptance check (**friend can run this without installing dependencies**):
1. On a clean Windows machine, run the EXE and click **Reconnect**.
2. Complete browser login.
3. Click **Refresh data** then **Export CSV** and verify quantity / stock / on_market columns populate.

### Milestone 4 — full multi-hub output and Windows executable packaging

Delivered:
- Multi-hub output is populated for Jita / Amarr / Dodixie / O-PNSN / C-N4OD.
- Added release packaging script to bundle EXE + config + README into a ZIP.
- Existing PyInstaller and Nuitka builds remain supported.

User-level acceptance check (**friend can run this without installing dependencies**):
1. Build and package with the provided scripts.
2. Send `release/BuilderLightweight-windows.zip` to a friend.
3. Friend extracts and runs `BuilderLightweightLauncher.exe` directly (no Python install).


## Static blueprint quantity profile

The calculator now includes a static build plan sourced from your provided blueprint list in `src/build_plan.py`:

- All listed blueprints are treated as fixed **ME 10 / TE 20** profiles.
- Duplicate blueprint rows are intentionally merged by summing quantities.
- CSV `quantity` column now exports the configured build quantity from this static plan.
- Build-cost computation is quantity-aware (batch-material rounding is applied before deriving per-unit cost), so larger runs benefit from ME exactly as requested.

## Run locally

If you're starting from GitHub, you do need to clone/download this repository first.

### Quick start (from GitHub)

```bash
git clone https://github.com/<your-org-or-user>/Builder_Lightweight.git
cd Builder_Lightweight
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m src.launcher
```

If you don't want to install Python locally, use the prebuilt Windows release ZIP after running the packaging script in this repo.

### Run locally (already downloaded)

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

## Package release ZIP (Windows)

```powershell
scripts\package_windows_release.bat
```

Expected output:
- `release\BuilderLightweight-windows.zip`

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
