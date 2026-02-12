from __future__ import annotations

import sys
from pathlib import Path
from tkinter import END, Button, Label, StringVar, Tk
from tkinter import filedialog, messagebox

from auth import EveSsoClient
from engine import CalculatorEngine


def bundled_path(file_name: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / file_name
    return Path(__file__).resolve().parent.parent / file_name


class LauncherApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("Builder Lightweight Launcher")
        self.status = StringVar(value="Ready")

        self.engine = CalculatorEngine(bundled_path("app_config.json"))
        esi_cfg = self.engine.config["esi"]
        self.sso = EveSsoClient(
            client_id=esi_cfg["client_id"],
            redirect_uri=esi_cfg["redirect_uri"],
            scopes=esi_cfg["scopes"],
        )

        Label(root, text="Builder Lightweight", font=("Segoe UI", 14, "bold")).pack(pady=(12, 8))

        Button(root, text="Login (EVE SSO)", width=24, command=self.login).pack(pady=4)
        Button(root, text="Refresh data", width=24, command=self.refresh_data).pack(pady=4)
        Button(root, text="Export CSV", width=24, command=self.export_csv).pack(pady=4)

        Label(root, textvariable=self.status).pack(pady=(10, 12))

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
            result = self.sso.login()
            self.status.set(f"Logged in. Token expires in {result.expires_in}s")
        except Exception as exc:
            self.status.set("Login failed")
            messagebox.showerror("EVE SSO login failed", str(exc))

    def refresh_data(self) -> None:
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
        path = self.engine.export_csv(Path(target))
        self.status.set(f"Exported CSV to {path}")
        messagebox.showinfo("Export complete", f"Saved to:\n{path}")


def main() -> None:
    root = Tk()
    root.geometry("380x230")
    LauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
