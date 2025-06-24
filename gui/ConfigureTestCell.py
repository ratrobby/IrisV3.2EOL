import os
import sys
from .utils import load_config, save_config
import subprocess
import tkinter as tk
from tkinter import ttk

# Paths used throughout the GUI
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEVICE_FOLDER = os.path.join(REPO_ROOT, "devices")
CONFIG_PATH = os.path.join(REPO_ROOT, "config", "Test_Cell_Config.json")

# Default configuration when no config file exists
DEFAULT_CONFIG = {
    "ip_address": "192.168.XXX.XXX",
    "al1342": {f"X{i:02d}": "Empty" for i in range(1, 9)},
    "al2205": {f"X1.{i}": "Empty" for i in range(8)},
}
DEFAULT_CONFIG["al1342"]["X01"] = "AL2205_Hub"
DEFAULT_CONFIG["al2205"]["X1.0"] = "UI_Button"


def get_device_options():
    """Return a sorted list of device module names."""
    modules = []
    for fname in os.listdir(DEVICE_FOLDER):
        if fname.endswith(".py") and fname != "__init__.py":
            modules.append(fname[:-3])
    return ["Empty"] + sorted(modules, key=str.lower)




class DeviceSelector(ttk.Frame):
    def __init__(self, parent, label, ports, options, locked=None):
        super().__init__(parent)
        self.vars = {}
        locked = locked or {}

        ttk.Label(self, text=label, font=("Arial", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 4))
        for row, port in enumerate(ports, start=1):
            ttk.Label(self, text=f"{port}:").grid(row=row, column=0, sticky="w", padx=5)
            var = tk.StringVar()
            cmb = ttk.Combobox(self, textvariable=var, values=options, state="readonly", width=28)
            cmb.grid(row=row, column=1, sticky="ew", padx=5, pady=1)
            if port in locked:
                var.set(locked[port])
                cmb.configure(state="disabled")
            self.vars[port] = var
        self.columnconfigure(1, weight=1)


class ConfigApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Configure Test Cell")
        self.wizard_procs = []

        options = get_device_options()
        cfg = load_config(CONFIG_PATH)

        # IP entry
        ip_frame = ttk.Frame(self)
        ip_frame.pack(fill="x", padx=10, pady=10)
        ttk.Label(ip_frame, text="AL1342 IP:").pack(side="left")
        self.ip_var = tk.StringVar(
            value=cfg.get("ip_address", DEFAULT_CONFIG["ip_address"])
        )
        ttk.Entry(ip_frame, textvariable=self.ip_var, width=20).pack(side="left", padx=5)

        # Device selector frames
        selector_frame = ttk.Frame(self)
        selector_frame.pack(fill="both", expand=True, padx=10)

        al1342_ports = [f"X{i:02d}" for i in range(1, 9)]
        al2205_ports = [f"X1.{i}" for i in range(8)]

        locked1342 = {"X01": "AL2205_Hub"}
        locked2205 = {"X1.0": "UI_Button"}

        self.sel1342 = DeviceSelector(selector_frame, "AL1342", al1342_ports, options, locked1342)
        self.sel1342.grid(row=0, column=0, padx=(0, 10), sticky="nsew")

        self.sel2205 = DeviceSelector(selector_frame, "AL2205", al2205_ports, options, locked2205)
        self.sel2205.grid(row=0, column=1, sticky="nsew")

        selector_frame.columnconfigure(0, weight=1)
        selector_frame.columnconfigure(1, weight=1)

        # Load existing selections
        for port, var in self.sel1342.vars.items():
            var.set(cfg.get("al1342", {}).get(port, "Empty"))
        for port, var in self.sel2205.vars.items():
            var.set(cfg.get("al2205", {}).get(port, "Empty"))

        # Configure button
        ttk.Button(self, text="Configure Test Cell", command=self.configure_cell).pack(pady=10)

    def gather_config(self):
        return {
            "ip_address": self.ip_var.get(),
            "al1342": {p: v.get() for p, v in self.sel1342.vars.items()},
            "al2205": {p: v.get() for p, v in self.sel2205.vars.items()},
        }

    def configure_cell(self):
        cfg = self.gather_config()
        save_config(cfg, CONFIG_PATH)
        self.launch_wizard()
        self.destroy()

    def launch_wizard(self):
        wizard_path = os.path.join(os.path.dirname(__file__), "TestWizard.py")
        proc = subprocess.Popen([sys.executable, wizard_path])
        self.wizard_procs.append(proc)

    def close_wizards(self):
        for p in getattr(self, "wizard_procs", []):
            if p.poll() is None:
                try:
                    p.terminate()
                    p.wait(timeout=2)
                except Exception:
                    try:
                        p.kill()
                    except Exception:
                        pass
        self.wizard_procs = []


if __name__ == "__main__":
    app = ConfigApp()
    app.mainloop()
