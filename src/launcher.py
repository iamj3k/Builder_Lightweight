from __future__ import annotations

import sys
from pathlib import Path
from tkinter import Button, Label, StringVar, Tk
from tkinter import filedialog, messagebox

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.auth import EveSsoClient
from src.engine import CalculatorEngine
from src.live_pricing import ConfigJitaLivePriceProvider


def bundled_path(file_name: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / file_name
    return Path(__file__).resolve().parent.parent / file_name


class LauncherApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("Builder Lightweight Launcher")
        self.status = StringVar(value="Ready")
        self.connection_state = StringVar(value="Reconnect")

        self.engine = CalculatorEngine(bundled_path("app_config.json"))
        self.live_pricing = ConfigJitaLivePriceProvider(self.engine.config)

        esi_cfg = self.engine.config["esi"]
        self.sso = EveSsoClient(
            client_id=esi_cfg["client_id"],
            redirect_uri=esi_cfg["redirect_uri"],
            scopes=esi_cfg["scopes"],
            token_store_path=Path.home() / ".builder_lightweight" / "sso_token.json",
        )
        self.connection_state.set(self.sso.connection_label())

        Label(root, text="Builder Lightweight", font=("Segoe UI", 14, "bold")).pack(pady=(12, 8))

        Button(root, textvariable=self.connection_state, width=24, command=self.login).pack(pady=4)
        Button(root, text="Refresh data", width=24, command=self.refresh_data).pack(pady=4)
        Button(root, text="Export CSV", width=24, command=self.export_csv).pack(pady=4)

        Label(root, textvariable=self.status).pack(pady=(10, 12))

    def _attach_character_state_from_config(self, access_token: str) -> None:
        overrides = self.engine.config.get("character_state_overrides", {})
        self.engine.attach_character_state(
            oauth_token=access_token,
            asset_rows=list(overrides.get("assets", [])),
            order_rows=list(overrides.get("open_orders", [])),
        )

    def login(self) -> None:
        if self.engine.config["esi"]["client_id"].startswith("REPLACE_WITH"):
            messagebox.showwarning(
                "Missing client ID",
                "Set esi.client_id in app_config.json before attempting login.",
            )
            return
        self.status.set("Logging in via EVE SSO...")
        self.root.update_idletasks()
        try:
            auth = self.sso.login()
            self._attach_character_state_from_config(auth.access_token)
            self.connection_state.set("Connected")
            self.status.set("Connected")
        except Exception:
            self.connection_state.set("Reconnect")
            self.status.set("Reconnect required")
            messagebox.showerror("Sign-in failed", "Unable to connect. Please try reconnecting.")

    def refresh_data(self) -> None:
        try:
            access_token = self.sso.ensure_access_token()
            self._attach_character_state_from_config(access_token)
            self.connection_state.set("Connected")
        except Exception:
            self.connection_state.set("Reconnect")
            self.status.set("Reconnect required")
            return

        results = self.engine.refresh_data()
        total = sum(item.total_cost for item in results)
        self.status.set(f"Refreshed {len(results)} blueprints. Total: {total:,.2f} ISK")

    def export_csv(self) -> None:
        target = filedialog.asksaveasfilename(
            title="Export CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if not target:
            return
        path = self.engine.export_csv(Path(target), live_price_provider=self.live_pricing)
        self.status.set(f"Exported CSV to {path}")
        messagebox.showinfo("Export complete", f"Saved to:\n{path}")


def main() -> None:
    root = Tk()
    root.geometry("380x230")
    LauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
