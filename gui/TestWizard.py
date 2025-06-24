import os
import sys
import json
import time
import threading
import queue
import subprocess
import importlib
import inspect
from contextlib import redirect_stdout
import re
import traceback

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText

# Allow running from repo root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(REPO_ROOT, "config", "Test_Cell_Config.json")
LOG_DIR = os.path.join(REPO_ROOT, "logs")
TESTS_DIR = os.path.join(REPO_ROOT, "user_tests")
DEVICES_FILE = os.path.join(REPO_ROOT, "config", "Test_Cell_1_Devices.py")


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as fh:
            try:
                return json.load(fh)
            except Exception:
                return {}
    return {}


def _normalize_instructions(cmds):
    """Return a list of instruction dictionaries with required keys."""
    if not isinstance(cmds, list):
        cmds = [cmds] if cmds else []
    result = []
    for item in cmds:
        if isinstance(item, dict) and "title" in item and "content" in item:
            result.append(item)
    return result


def gather_library(cfg):
    """Return dict of setup and test instructions from configured devices.

    The returned structure groups commands by device class name so the GUI can
    display them in labeled sections.
    """
    library = {"setup": {}, "test": {}}
    modules = set()
    modules.update(v for v in cfg.get("al1342", {}).values() if v != "Empty")
    modules.update(v for v in cfg.get("al2205", {}).values() if v != "Empty")

    import_errors = []

    for mod_name in sorted(modules):
        try:
            mod = importlib.import_module(f"devices.{mod_name}")
        except Exception as e:
            msg = f"Failed to import device module '{mod_name}': {e}"
            print(msg)
            import_errors.append(msg)
            continue
        device_cls = None
        for name, obj in inspect.getmembers(mod, inspect.isclass):
            if getattr(obj, "_is_device_class", False):
                device_cls = obj
                break
        if not device_cls:
            continue

        if hasattr(device_cls, "setup_instructions"):
            try:
                cmds = _normalize_instructions(device_cls.setup_instructions())
                if cmds:
                    library["setup"][device_cls.__name__] = cmds
            except Exception as e:
                print(
                    f"Failed to load setup instructions for {device_cls.__name__}: {e}"
                )
        if hasattr(device_cls, "test_instructions"):
            try:
                cmds = _normalize_instructions(device_cls.test_instructions())
                if cmds:
                    library["test"][device_cls.__name__] = cmds
            except Exception as e:
                print(
                    f"Failed to load test instructions for {device_cls.__name__}: {e}"
                )

    if import_errors:
        try:
            messagebox.showerror("Device Import Error", "\n".join(import_errors))
        except Exception:
            pass

    return library


def build_instance_map(cfg):
    """Return mapping of ports to instance names for each AL section.

    If only one instance of a given device is present across both sections,
    the instance name will simply be the device name. When multiple devices of
    the same type are connected, each instance is numbered starting from
    ``device_1``.
    """

    # Count how many times each device appears across all sections
    device_totals = {}
    for section in ("al1342", "al2205"):
        for port in cfg.get(section, {}):
            device = cfg.get(section, {}).get(port, "Empty")
            if str(device).lower() == "empty":
                continue
            device_totals[device] = device_totals.get(device, 0) + 1

    # Track numbering for devices that appear more than once
    counts = {}
    result = {"al1342": {}, "al2205": {}}
    for section in ("al1342", "al2205"):
        for port in sorted(cfg.get(section, {})):
            device = cfg.get(section, {}).get(port, "Empty")
            if str(device).lower() == "empty":
                result[section][port] = "Empty"
                continue

            if device_totals.get(device, 0) == 1:
                # Only one device of this type, no numbering
                result[section][port] = device
            else:
                idx = counts.get(device, 0) + 1
                counts[device] = idx
                result[section][port] = f"{device}_{idx}"
    return result


class TestMonitor(tk.Toplevel):
    """Simple window that displays test output."""

    def __init__(self, master):
        super().__init__(master)
        self.title("Test Monitor")
        self.geometry("600x400")
        self.text = ScrolledText(self, state="disabled")
        self.text.pack(fill="both", expand=True)

    def append(self, message):
        self.text.configure(state="normal")
        self.text.insert("end", message)
        self.text.see("end")
        self.text.configure(state="disabled")


class _QueueWriter:
    def __init__(self, q):
        self.q = q

    def write(self, msg):
        self.q.put(msg)

    def flush(self):
        pass


class _Tee:
    def __init__(self, *writers):
        self.writers = writers

    def write(self, msg):
        for w in self.writers:
            w.write(msg)

    def flush(self):
        for w in self.writers:
            if hasattr(w, "flush"):
                w.flush()


class TestWizard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Test Wizard")
        self.cfg = load_config()
        self.ip_address = self.cfg.get("ip_address", "192.168.XXX.XXX")
        self.library = gather_library(self.cfg)
        self.base_map = build_instance_map(self.cfg)
        self.instance_map = {s: dict(p) for s, p in self.base_map.items()}
        self._apply_custom_names()

        self.running = False
        self.paused = False
        self.worker = None
        self.log_file = None
        self.test_file_path = None
        self.monitor = None
        self.monitor_queue = queue.Queue()

        self.create_widgets()
        # Scale window after widgets have been laid out
        self.update_idletasks()
        # Position the window at x=100, y=50
        self.geometry("1600x950+150+20")
        self.check_connection()
        self.after(100, self.poll_monitor_queue)

    def _load_custom_names(self):
        """Return mapping of original instance names to custom aliases."""
        try:
            with open(DEVICES_FILE, "r") as fh:
                lines = fh.read().splitlines()
        except Exception:
            return {}
        start_marker = "# --- Custom Instance Names ---"
        end_marker = "# --- End Custom Instance Names ---"
        mapping = {}
        if start_marker in lines:
            s = lines.index(start_marker)
            if end_marker in lines[s:]:
                e = s + lines[s:].index(end_marker)
                for line in lines[s + 1 : e]:
                    if "=" in line:
                        alias, orig = line.split("=", 1)
                        mapping[orig.strip().lower()] = alias.strip()
        return mapping

    def _apply_custom_names(self):
        mapping = self._load_custom_names()
        for section in ("al1342", "al2205"):
            for port, orig in self.base_map[section].items():
                alias = mapping.get(orig.lower())
                if alias:
                    self.instance_map[section][port] = alias

    # ----------------------- GUI Construction -----------------------
    def create_widgets(self):
        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=10, pady=10)

        # Style for highlighted open command boxes
        self.style = ttk.Style(self)
        self.style.configure("Open.TFrame", background="#e8f0fe")
        self.style.configure("TestName.TLabel", font=("Segoe UI Variable Display Semib", 12,))

        # Main content split into left and right columns
        content = ttk.Frame(main)
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=2)
        content.rowconfigure(0, weight=1)

        # ----------------------- Left Column -----------------------
        left = ttk.Frame(content)
        left.grid(row=0, column=0, sticky="nsew")
        left.columnconfigure(0, weight=1)

        name_frame = ttk.Frame(left)
        name_frame.grid(row=0, column=0, sticky="ew")
        name_frame.columnconfigure(0, weight=1)

        ttk.Label(name_frame, text="Test Name:", style="TestName.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 5)
        )
        self.test_name_var = tk.StringVar()
        self.test_name_entry = ttk.Entry(
            name_frame, textvariable=self.test_name_var, font=("Arial", 12)
        )
        self.test_name_entry.grid(row=1, column=0, sticky="ew", padx=5, ipady=4)

        ttk.Button(name_frame, text="Browse", command=self.browse_test_file).grid(
            row=1, column=1, padx=5
        )

        ttk.Label(left, text="Test Setup:", style="TestName.TLabel").grid(
            row=1, column=0, sticky="w", pady=(20, 0)
        )
        self.setup_text = ScrolledText(left, height=8)
        self.setup_text.grid(row=2, column=0, sticky="nsew", pady=(5, 20))
        self.setup_text.insert("end", "# Setup code\n")
        left.rowconfigure(2, weight=1)

        ttk.Label(left, text="Test Loop:", style="TestName.TLabel").grid(
            row=3, column=0, sticky="w"
        )
        self.script_text = ScrolledText(left, height=12)
        self.script_text.grid(row=4, column=0, sticky="nsew", pady=(5, 0))
        self.script_text.insert("end", "# Test loop code\n")
        left.rowconfigure(4, weight=1)

        # ----------------------- Right Column ----------------------
        right = ttk.Frame(content)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        right.columnconfigure(0, weight=1)

        inst_status = ttk.Frame(right)
        inst_status.pack(fill="x", padx=5, pady=(0, 5))
        inst_status.columnconfigure(0, weight=1)
        inst_status.columnconfigure(1, weight=1)
        inst_status.rowconfigure(0, weight=1)
        inst_status.rowconfigure(1, weight=1)

        map_frame = None
        if self.instance_map:
            map_frame = ttk.LabelFrame(inst_status, text="Device Instances")
            map_frame.grid(row=0, column=0, sticky="nsew")

            col1 = ttk.Frame(map_frame)
            col2 = ttk.Frame(map_frame)
            col1.pack(side="left", padx=5)
            col2.pack(side="left", padx=5)

            ttk.Label(col1, text="AL1342").grid(row=0, column=0, columnspan=2)
            ttk.Label(col2, text="AL2205").grid(row=0, column=0, columnspan=2)

            self.name_vars = {"al1342": {}, "al2205": {}}

            for r, port in enumerate(sorted(self.instance_map["al1342"]), start=1):
                ttk.Label(col1, text=f"{port}:").grid(row=r, column=0, sticky="e", pady=1)
                var = tk.StringVar(value=self.instance_map["al1342"][port])
                self.name_vars["al1342"][port] = var
                entry = ttk.Entry(col1, textvariable=var, width=23)
                if self.cfg.get("al1342", {}).get(port) == "AL2205_Hub":
                    entry.configure(state="disabled")
                entry.grid(row=r, column=1, sticky="w")

            for r, port in enumerate(sorted(self.instance_map["al2205"]), start=1):
                ttk.Label(col2, text=f"{port}:").grid(row=r, column=0, sticky="e", pady=1)
                var = tk.StringVar(value=self.instance_map["al2205"][port])
                self.name_vars["al2205"][port] = var
                entry = ttk.Entry(col2, textvariable=var, width=23)
                if self.cfg.get("al2205", {}).get(port) == "UI_Button":
                    entry.configure(state="disabled")
                entry.grid(row=r, column=1, sticky="w")

            ttk.Button(
                inst_status,
                text="Update Device Naming",
                command=self.update_device_naming,
            ).grid(row=1, column=0, columnspan=2, pady=(4, 2))

        status_frame = ttk.LabelFrame(inst_status, text="AL1342 Connection Status:")
        status_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self.status_var = tk.StringVar(value="Disconnected")

        # Container with a border to make the status more visible
        status_box = ttk.Frame(status_frame, borderwidth=2, relief="groove", padding=2)
        status_box.pack(expand=True, fill="both", padx=5, pady=5)

        self.status_label = ttk.Label(
            status_box,
            textvariable=self.status_var,
            foreground="red",
            font=("Arial", 12),
            anchor="center",  # center text
            justify="center"
        )
        self.status_label.pack(expand=True, fill="both")

        # Collapsible command library below the device instances
        lib_label = ttk.Label(
            right, text="Command Library", font=("Arial", 12, "bold")
        )
        lib_frame = ttk.LabelFrame(right, labelwidget=lib_label)
        lib_frame.pack(fill="both", expand=True, padx=5, pady=5)
        lib_frame.columnconfigure(0, weight=1)

        setup_label = ttk.Label(
            lib_frame, text="Setup Commands", font=("Arial", 11, "underline")
        )
        setup_container = ttk.LabelFrame(lib_frame, labelwidget=setup_label)
        setup_container.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        for device, cmds in self.library["setup"].items():
            ttk.Label(
                setup_container, text=device, font=("Arial", 10, "bold")
            ).pack(anchor="w", pady=0)
            dev_frame = ttk.Frame(setup_container)
            dev_frame.pack(fill="x", padx=10, pady=(0, 5))
            for cmd in cmds:
                self._create_collapsible_text(
                    dev_frame, cmd["title"], cmd["content"]
                )

        test_label = ttk.Label(
            lib_frame, text="Test Commands", font=("Arial", 11, "underline")
        )
        test_container = ttk.LabelFrame(lib_frame, labelwidget=test_label)
        test_container.pack(fill="both", expand=True, padx=5, pady=5)
        for device, cmds in self.library["test"].items():
            ttk.Label(test_container, text=device, font=("Arial", 10, "bold")).pack(anchor="w", pady=0)
            dev_frame = ttk.Frame(test_container)
            dev_frame.pack(fill="x", padx=10, pady=(0, 2))  # <- updated
            for cmd in cmds:
                self._create_collapsible_text(dev_frame, cmd["title"], cmd["content"])

        # The lower test editor has been removed to avoid duplication. The
        # primary test loop editor remains in the left column above.
        # Buttons
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill="x", pady=10)
        self.start_btn = ttk.Button(btn_frame, text="Start", command=self.start_test)
        self.stop_btn = ttk.Button(btn_frame, text="Stop", command=self.stop_test, state="disabled")
        self.pause_btn = ttk.Button(btn_frame, text="Pause", command=self.toggle_pause, state="disabled")
        self.start_btn.pack(side="left", padx=5)
        self.stop_btn.pack(side="left", padx=5)
        self.pause_btn.pack(side="left", padx=5)

        self.save_btn = ttk.Button(btn_frame, text="Save Test", command=self.save_test)
        self.new_btn = ttk.Button(btn_frame, text="New Test", command=self.new_test)
        self.reconfig_btn = ttk.Button(
            btn_frame,
            text="Reconfigure Test Cell",
            command=self.reconfigure_cell,
        )
        self.reconfig_btn.pack(side="right", padx=5)
        self.new_btn.pack(side="right", padx=5)
        self.save_btn.pack(side="right", padx=5)


    def _create_collapsible_text(self, parent, section_title, content):
        if not section_title or not str(section_title).strip():
            section_title = "<Untitled Command>"

        container = ttk.Frame(parent, relief="groove", borderwidth=1)
        container.pack(fill="x", pady=(0, 2), padx=5)

        header = ttk.Frame(container)
        header.pack(fill="x")

        title_label = ttk.Label(header, text=section_title, font=("Arial", 10, "bold italic"))
        title_label.pack(side="left", padx=5, pady=(2, 0))

        arrow_label = ttk.Label(header, text="\u25BC")  # Down arrow
        arrow_label.pack(side="right", padx=5)

        text_widget = tk.Text(
            container,
            wrap="word",
            height=1,
            width=60,
            font=("Arial", 9),
            background="#f5f5f5",
        )
        text_widget.insert("1.0", content)

        # Temporarily display to measure required width and then hide again
        text_widget.pack(fill="x", padx=15, pady=2)
        text_widget.update_idletasks()
        container.configure(width=text_widget.winfo_width())
        header_height = header.winfo_reqheight()
        text_widget.pack_forget()
        container.update_idletasks()
        container.configure(height=header_height)
        container.pack_propagate(False)  # keep width constant and maintain header height

        keyword_styles = {
            "Command:": "command_style",
            "Inputs:": "bold",
            "Example:": "bold",
            "Use:": "bold",
        }

        for keyword, tag in keyword_styles.items():
            start = "1.0"
            while True:
                pos = text_widget.search(keyword, start, stopindex="end")
                if not pos:
                    break
                end = f"{pos}+{len(keyword)}c"
                text_widget.tag_add(tag, pos, end)
                start = end

        text_widget.tag_configure("bold", font=("Arial", 10, "bold"))
        text_widget.tag_configure("command_style", font=("Arial", 11, "bold"), foreground="#003366")
        text_widget.configure(state="disabled", height=min(30, content.count("\n") + 2))
        text_widget.update_idletasks()
        open_height = header_height + text_widget.winfo_reqheight()

        def toggle():
            if text_widget.winfo_viewable():
                text_widget.pack_forget()
                container.configure(height=header_height)
                arrow_label.configure(text="\u25BC")
                container.configure(style="TFrame")
            else:
                text_widget.pack(fill="x", padx=15, pady=2)
                container.configure(height=open_height)
                arrow_label.configure(text="\u25B2")
                container.configure(style="Open.TFrame")

        header.bind("<Button-1>", lambda e: toggle())
        title_label.bind("<Button-1>", lambda e: toggle())
        arrow_label.bind("<Button-1>", lambda e: toggle())

    def update_device_naming(self):
        """Write custom device name aliases to ``Test_Cell_1_Devices.py``."""
        alias_lines = []
        for section in ("al1342", "al2205"):
            for port, var in self.name_vars.get(section, {}).items():
                new_name = var.get().strip()
                base = self.base_map[section][port].lower()
                if new_name and new_name != base:
                    alias_lines.append(f"{new_name} = {base}")
                    self.instance_map[section][port] = new_name
                else:
                    self.instance_map[section][port] = base

        try:
            with open(DEVICES_FILE, "r") as fh:
                lines = fh.read().splitlines()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read {DEVICES_FILE}: {e}")
            return

        start_marker = "# --- Custom Instance Names ---"
        end_marker = "# --- End Custom Instance Names ---"
        if start_marker in lines:
            s = lines.index(start_marker)
            if end_marker in lines[s:]:
                e = s + lines[s:].index(end_marker)
                del lines[s : e + 1]

        if alias_lines:
            lines.append("")
            lines.append(start_marker)
            lines.extend(alias_lines)
            lines.append(end_marker)
            lines.append("")

        try:
            with open(DEVICES_FILE, "w") as fh:
                fh.write("\n".join(lines))
            messagebox.showinfo("Success", "Device names updated")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to write {DEVICES_FILE}: {e}")

    # ----------------------- Connection Status ---------------------
    def check_connection(self):
        try:
            if os.name == "nt":
                cmd = ["ping", "-n", "1", "-w", "1000", self.ip_address]
            else:
                cmd = ["ping", "-c", "1", "-W", "1", self.ip_address]
            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            ok = result.returncode == 0
        except Exception:
            ok = False
        self.status_var.set("Connected" if ok else "Disconnected")
        self.status_label.configure(foreground="green" if ok else "red")
        self.after(1000, self.check_connection)

    def poll_monitor_queue(self):
        while not self.monitor_queue.empty():
            msg = self.monitor_queue.get()
            if self.monitor and self.monitor.winfo_exists():
                self.monitor.append(msg)
        self.after(100, self.poll_monitor_queue)

    # ----------------------- Test Execution ------------------------
    def start_test(self):
        if self.running:
            return
        os.makedirs(LOG_DIR, exist_ok=True)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        name = self.test_name_var.get() or "test"
        log_path = os.path.join(LOG_DIR, f"{timestamp}_{name}.log")
        self.log_file = open(log_path, "w")
        if not self.monitor or not self.monitor.winfo_exists():
            self.monitor = TestMonitor(self)
        else:
            self.monitor.deiconify()
            self.monitor.lift()
        self.running = True
        self.paused = False
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.pause_btn.configure(state="normal", text="Pause")
        context = {"__name__": "__main__"}
        try:
            devices_mod = importlib.import_module("config.Test_Cell_1_Devices")
            for name, obj in devices_mod.__dict__.items():
                if not name.startswith("_"):
                    context[name] = obj
        except Exception as e:
            print(f"Failed to load device objects: {e}")
        setup_code = self.setup_text.get("1.0", "end-1c")
        loop_code = self.script_text.get("1.0", "end-1c")
        queue_writer = _QueueWriter(self.monitor_queue)
        def worker():
            with redirect_stdout(_Tee(self.log_file, queue_writer)):
                try:
                    exec(setup_code, context)
                except Exception as e:
                    print(f"Setup error: {e}")
                    self.running = False
                    return
                while self.running:
                    if self.paused:
                        time.sleep(0.1)
                        continue
                    try:
                        exec(loop_code, context)
                    except Exception as e:
                        print(f"Loop error: {e}")
                        self.running = False
                        break
            self.log_file.close()
        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()

    def stop_test(self):
        if not self.running:
            return
        self.running = False
        if self.worker:
            self.worker.join(timeout=2)
        if self.log_file and not self.log_file.closed:
            self.log_file.close()
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.pause_btn.configure(state="disabled")

    def toggle_pause(self):
        if not self.running:
            return
        self.paused = not self.paused
        self.pause_btn.configure(text="Resume" if self.paused else "Pause")

    # ----------------------- Test File Handling -------------------
    def save_test(self):
        name = self.test_name_var.get().strip()
        if not name:
            messagebox.showerror("Error", "Please enter a test name.")
            return
        os.makedirs(TESTS_DIR, exist_ok=True)
        fname = re.sub(r"\W+", "_", name)
        path = os.path.join(TESTS_DIR, f"{fname}.json")
        data = {
            "name": name,
            "setup": self.setup_text.get("1.0", "end-1c"),
            "loop": self.script_text.get("1.0", "end-1c"),
        }
        try:
            with open(path, "w") as fh:
                json.dump(data, fh, indent=2)
            self.test_file_path = path
            messagebox.showinfo("Saved", f"Test saved to {path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save test: {e}")

    def load_test(self, path):
        if not path:
            return
        try:
            with open(path, "r") as fh:
                data = json.load(fh)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load test: {e}")
            return
        self.test_file_path = path
        self.test_name_var.set(data.get("name", ""))
        self.setup_text.delete("1.0", "end")
        self.setup_text.insert("1.0", data.get("setup", ""))
        self.script_text.delete("1.0", "end")
        self.script_text.insert("1.0", data.get("loop", ""))

    def browse_test_file(self):
        path = filedialog.askopenfilename(
            initialdir=TESTS_DIR,
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
        )
        if path:
            self.load_test(path)

    def new_test(self):
        current_filled = (
            self.test_name_var.get().strip()
            or self.setup_text.get("1.0", "end-1c").strip()
            or self.script_text.get("1.0", "end-1c").strip()
        )
        if current_filled:
            if messagebox.askyesno("Save Test", "Save current test before creating a new test?"):
                self.save_test()
        self.test_file_path = None
        self.test_name_var.set("")
        self.setup_text.delete("1.0", "end")
        self.setup_text.insert("1.0", "# Setup code\n")
        self.script_text.delete("1.0", "end")
        self.script_text.insert("1.0", "# Test loop code\n")

    def reconfigure_cell(self):
        current_filled = (
            self.test_name_var.get().strip()
            or self.setup_text.get("1.0", "end-1c").strip()
            or self.script_text.get("1.0", "end-1c").strip()
        )
        if current_filled:
            if messagebox.askyesno(
                "Save Test",
                "Save current test before reconfiguring the test cell?",
            ):
                self.save_test()
        config_path = os.path.join(os.path.dirname(__file__), "ConfigureTestCell.py")
        subprocess.Popen([sys.executable, config_path])
        self.destroy()


if __name__ == "__main__":
    app = TestWizard()
    app.mainloop()
