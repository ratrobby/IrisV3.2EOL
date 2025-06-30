import os
import re
import sys
import shutil
import json
from .utils import load_config, save_config, export_device_setup
from .TestWizard import build_instance_map
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Paths used throughout the GUI
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEVICE_FOLDER = os.path.join(REPO_ROOT, "devices")
CONFIG_PATH = os.path.join(REPO_ROOT, "config", "Test_Cell_Config.json")
TEST_BASE_DIR = os.path.expanduser(
    os.environ.get(
        "MRLF_TEST_DIR",
        os.path.join(REPO_ROOT, "user_tests"),
    )
)

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
    def __init__(self, parent, label, ports, options, locked=None, names=None, base_names=None):
        super().__init__(parent)
        self.vars = {}
        self.name_vars = {}
        locked = locked or {}
        names = names or {}
        base_names = base_names or {}

        ttk.Label(self, text=label, font=("Arial", 12, "bold")).grid(
            row=0, column=0, columnspan=3, pady=(0, 4)
        )
        ttk.Label(
            self,
            text="Map Devices to Port",
            font=("Arial", 10, "underline"),
        ).grid(row=1, column=1, pady=(0, 4))
        ttk.Label(
            self,
            text="Define Device Name",
            font=("Arial", 10, "underline"),
        ).grid(row=1, column=2, pady=(0, 4))
        for row, port in enumerate(ports, start=2):
            ttk.Label(self, text=f"{port}:").grid(row=row, column=0, sticky="w", padx=5)
            var = tk.StringVar()
            cmb = ttk.Combobox(self, textvariable=var, values=options, state="readonly", width=28)
            cmb.grid(row=row, column=1, sticky="ew", padx=5, pady=1)
            if port in names:
                default_name = names[port]
            elif port in locked:
                default_name = base_names.get(port, "")
            else:
                default_name = "Enter Name"
            name_var = tk.StringVar(value=default_name)
            ent = ttk.Entry(self, textvariable=name_var, width=20)
            ent.grid(row=row, column=2, sticky="ew", padx=5, pady=1)
            if port in locked:
                var.set(locked[port])
                cmb.configure(state="disabled")
                ent.configure(state="disabled")
            self.vars[port] = var
            self.name_vars[port] = name_var
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=1)


class TestLauncher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Test Launcher")
        self.wizard_procs = []

        options = get_device_options()
        cfg = load_config(CONFIG_PATH)
        base_map = build_instance_map(cfg)
        # Device instance names are not persisted; start with empty values
        name_map = {}

        name_frame = ttk.Frame(self)
        name_frame.pack(fill="x", padx=10, pady=(10, 0))
        ttk.Label(name_frame, text="Test Name:").pack(side="left")
        self.test_name_var = tk.StringVar()
        ttk.Entry(name_frame, textvariable=self.test_name_var, width=30).pack(side="left", padx=5)

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

        self.sel1342 = DeviceSelector(
            selector_frame,
            "AL1342",
            al1342_ports,
            options,
            locked1342,
            names=name_map.get("al1342", {}),
            base_names=base_map.get("al1342", {}),
        )
        self.sel1342.configure(borderwidth=2, relief="groove", padding=5)
        self.sel1342.grid(row=0, column=0, padx=(0, 10), sticky="nsew")

        self.sel2205 = DeviceSelector(
            selector_frame,
            "AL2205",
            al2205_ports,
            options,
            locked2205,
            names=name_map.get("al2205", {}),
            base_names=base_map.get("al2205", {}),
        )
        self.sel2205.configure(borderwidth=2, relief="groove", padding=5)
        self.sel2205.grid(row=0, column=1, sticky="nsew")

        selector_frame.columnconfigure(0, weight=1)
        selector_frame.columnconfigure(1, weight=1)

        # Load existing selections
        for port, var in self.sel1342.vars.items():
            var.set(cfg.get("al1342", {}).get(port, "Empty"))
        for port, var in self.sel2205.vars.items():
            var.set(cfg.get("al2205", {}).get(port, "Empty"))

        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Create New Test", command=self.create_test).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Load Test From File", command=self.load_test).pack(side="left", padx=5)

    def launch_wizard(self, test_name=None, test_dir=None, load_file=None, script_path=None):
      
        """Start ``gui.TestWizard`` in a separate process."""
        cmd = [sys.executable, "-m", "gui.TestWizard"]
        if test_name:
            cmd += ["--test-name", test_name]
        if test_dir:
            cmd += ["--test-dir", test_dir]
        if load_file:
            cmd += ["--load-file", load_file]

        env = os.environ.copy()
        if script_path:
            env["MRLF_TEST_SCRIPT"] = script_path
        proc = subprocess.Popen(cmd, cwd=REPO_ROOT, env=env)
        self.wizard_procs.append(proc)

    def gather_config(self):
        cfg = {
            "ip_address": self.ip_var.get(),
            "al1342": {p: v.get() for p, v in self.sel1342.vars.items()},
            "al2205": {p: v.get() for p, v in self.sel2205.vars.items()},
        }
        base_map = build_instance_map(cfg)
        names = {"al1342": {}, "al2205": {}}
        for port, var in self.sel1342.name_vars.items():
            val = var.get().strip()
            if not val or val == "Enter Name":
                alias = base_map["al1342"][port]
            else:
                alias = val
            names["al1342"][port] = alias
        for port, var in self.sel2205.name_vars.items():
            val = var.get().strip()
            if not val or val == "Enter Name":
                alias = base_map["al2205"][port]
            else:
                alias = val
            names["al2205"][port] = alias
        cfg["device_names"] = names
        return cfg

    def create_test(self):
        name = self.test_name_var.get().strip()
        if not name:
            messagebox.showerror("Error", "Please enter a test name")
            return
        cfg = self.gather_config()
        # Persist only device selections and IP address, not custom names
        persistent_cfg = {
            "ip_address": cfg["ip_address"],
            "al1342": cfg["al1342"],
            "al2205": cfg["al2205"],
        }
        save_config(persistent_cfg, CONFIG_PATH)
        safe = re.sub(r"\W+", "_", name)
        test_dir = os.path.join(TEST_BASE_DIR, safe)

        if os.path.exists(test_dir):
            overwrite = messagebox.askyesno(
                "Test Name already Exists",
                "Test Name already Exists. Overwrite the existing test data?",
            )
            if not overwrite:
                return
            try:
                shutil.rmtree(test_dir)
            except Exception as e:
                messagebox.showerror(
                    "Error",
                    f"Failed to overwrite existing test data: {e}",
                )
                return
        os.makedirs(test_dir, exist_ok=True)
        script_path = os.path.join(test_dir, f"{safe}_Script.py")
        export_device_setup(cfg, path=script_path)
        self.launch_wizard(test_name=name, test_dir=test_dir, script_path=script_path)

    def load_test(self):
        path = filedialog.askopenfilename(initialdir=TEST_BASE_DIR,
                                          filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")])
        if path:
            try:
                with open(path, "r") as fh:
                    data = json.load(fh)
                script_path = os.path.join(os.path.dirname(path), data.get("script_file", ""))
            except Exception:
                script_path = None
            self.launch_wizard(load_file=path, script_path=script_path)
            self.destroy()

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
    app = TestLauncher()
    app.mainloop()
