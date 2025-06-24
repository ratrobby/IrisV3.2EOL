import os
import sys
import json
import time
import threading
import subprocess
import importlib
import inspect
from contextlib import redirect_stdout
import re

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText

# Allow running from repo root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(REPO_ROOT, "config", "Test_Cell_Config.json")
LOG_DIR = os.path.join(REPO_ROOT, "logs")
TESTS_DIR = os.path.join(REPO_ROOT, "user_tests")


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as fh:
            try:
                return json.load(fh)
            except Exception:
                return {}
    return {}


def gather_library(cfg):
    """Return dict of setup and test instructions from configured devices."""
    setup_cmds = []
    test_cmds = []
    modules = set()
    modules.update(v for v in cfg.get("al1342", {}).values() if v != "Empty")
    modules.update(v for v in cfg.get("al2205", {}).values() if v != "Empty")

    for mod_name in modules:
        try:
            mod = importlib.import_module(f"devices.{mod_name}")
        except Exception:
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
                setup_cmds.append(device_cls.setup_instructions())
            except Exception:
                pass

        if hasattr(device_cls, "test_instruction"):
            try:
                test_cmds.append(device_cls.test_instruction())
            except Exception:
                pass
        elif hasattr(device_cls, "test_instructions"):
            try:
                test_cmds.append(device_cls.test_instructions())
            except Exception:
                pass

    return {"setup": setup_cmds, "test": test_cmds}


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
                result[section][port] = "empty"
                continue

            if device_totals.get(device, 0) == 1:
                # Only one device of this type, no numbering
                result[section][port] = device
            else:
                idx = counts.get(device, 0) + 1
                counts[device] = idx
                result[section][port] = f"{device}_{idx}"
    return result


class TestWizard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Test Wizard")
        self.cfg = load_config()
        self.ip_address = self.cfg.get("ip_address", "192.168.XXX.XXX")
        self.library = gather_library(self.cfg)
        self.instance_map = build_instance_map(self.cfg)

        self.running = False
        self.paused = False
        self.worker = None
        self.log_file = None
        self.test_file_path = None

        self.create_widgets()
        # Scale window after widgets have been laid out
        self.update_idletasks()
        self.geometry("1600x950")
        self.check_connection()

    # ----------------------- GUI Construction -----------------------
    def create_widgets(self):
        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=10, pady=10)

        # Style for highlighted open command boxes
        self.style = ttk.Style(self)
        self.style.configure("Open.TFrame", background="#e8f0fe")
        self.style.configure("TestName.TLabel", font=("Arial", 12, "bold"))

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
        name_frame.columnconfigure(1, weight=1)

        ttk.Label(name_frame, text="Test Name:", style="TestName.TLabel").grid(row=0, column=0, sticky="w")
        self.test_name_var = tk.StringVar()
        self.test_name_entry = ttk.Entry(name_frame, textvariable=self.test_name_var, font=("Arial", 12))
        self.test_name_entry.grid(row=0, column=1, sticky="ew", padx=5, ipady=4)

        ttk.Button(name_frame, text="Browse", command=self.browse_test_file).grid(row=0, column=2, padx=5)

        self.setup_text = ScrolledText(left, height=8)
        self.setup_text.grid(row=1, column=0, sticky="nsew", pady=(30, 20))
        self.setup_text.insert("end", "# Setup code\n")
        left.rowconfigure(1, weight=1)

        self.script_text = ScrolledText(left, height=12)
        self.script_text.grid(row=2, column=0, sticky="nsew", pady=(5, 0))
        self.script_text.insert("end", "# Test loop code\n")
        left.rowconfigure(2, weight=1)

        # ----------------------- Right Column ----------------------
        right = ttk.Frame(content)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        right.columnconfigure(0, weight=1)

        status_frame = ttk.LabelFrame(right, text="AL1342 Connection Status:")
        status_frame.pack(anchor="n")
        status_frame.pack_propagate(False)
        self.status_var = tk.StringVar(value="Disconnected")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, foreground="red")
        self.status_label.pack(padx=5, pady=2)

        def _resize_status(event):
            width = event.width
            frame_width = width // 2
            status_frame.configure(width=frame_width)
            status_frame.pack_configure(padx=(width - frame_width) // 2)

        right.bind("<Configure>", _resize_status)

        if self.instance_map:
            map_frame = ttk.LabelFrame(right, text="Device Instances")
            map_frame.pack(fill="x", padx=5, pady=(5, 0))

            col1 = ttk.Frame(map_frame)
            col2 = ttk.Frame(map_frame)
            col1.pack(side="left", padx=2)
            col2.pack(side="left", padx=2)

            ttk.Label(col1, text="AL1342").pack()
            ttk.Label(col2, text="AL2205").pack()

            height = max(len(self.instance_map["al1342"]), len(self.instance_map["al2205"]))
            height = min(height, 10) or 1

            entries1342 = [f"{p}: {self.instance_map['al1342'][p]}" for p in sorted(self.instance_map['al1342'])]
            entries2205 = [f"{p}: {self.instance_map['al2205'][p]}" for p in sorted(self.instance_map['al2205'])]
            width1342 = max((len(e) for e in entries1342), default=10) + 1
            width2205 = max((len(e) for e in entries2205), default=10) + 1

            bg = self.cget("bg")
            self.map_list1342 = tk.Listbox(col1, height=height, width=width1342, bg=bg)
            self.map_list2205 = tk.Listbox(col2, height=height, width=width2205, bg=bg)
            self.map_list1342.pack()
            self.map_list2205.pack()

            for line in entries1342:
                self.map_list1342.insert("end", line)

            for line in entries2205:
                self.map_list2205.insert("end", line)

        # Collapsible command library below the device instances
        lib_frame = ttk.LabelFrame(right, text="Command Library")
        lib_frame.pack(fill="both", expand=True, padx=5, pady=5)
        lib_frame.columnconfigure(0, weight=1)

        ttk.Label(lib_frame, text="Setup Commands").pack(anchor="w")
        setup_container = ttk.Frame(lib_frame)
        setup_container.pack(fill="both", expand=True, padx=5, pady=2)
        for instr in self.library["setup"]:
            for title, content in self._parse_commands(instr, "Test Setup Commands"):
                self._create_collapsible_text(setup_container, title, content)

        ttk.Label(lib_frame, text="Test Commands").pack(anchor="w", pady=(5, 0))
        test_container = ttk.Frame(lib_frame)
        test_container.pack(fill="both", expand=True, padx=5, pady=2)
        for instr in self.library["test"]:
            for title, content in self._parse_commands(instr, "Test Commands"):
                self._create_collapsible_text(test_container, title, content)

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

    def _extract_section(self, instructions, section_title):
        pattern = rf"{section_title}\s*:(.*?)(\n[A-Z].*?:|\Z)"
        match = re.search(pattern, instructions, re.DOTALL)
        return match.group(1).strip() if match else instructions.strip()

    def _split_commands(self, text):
        commands = []
        current_title = None
        lines = []
        for line in text.splitlines():
            if line.strip().startswith("Command:"):
                if current_title:
                    commands.append((current_title, "\n".join(lines).strip()))
                    lines = []
                # Extract title between ~ symbols if present
                m = re.search(r"~(.*?)~", line)
                current_title = m.group(1).strip() if m else line.replace("Command:", "").strip()
            else:
                lines.append(line)
        if current_title:
            commands.append((current_title, "\n".join(lines).strip()))
        return commands

    def _parse_commands(self, instructions, section_title=None):
        if section_title:
            instructions = self._extract_section(instructions, section_title)
        return self._split_commands(instructions)

    def _create_collapsible_text(self, parent, section_title, content):
        container = ttk.Frame(parent, relief="groove", borderwidth=1)
        container.pack(fill="x", pady=2, padx=5)
        container.pack_propagate(False)  # keep width constant

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
        text_widget.pack_forget()

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

        def toggle():
            if text_widget.winfo_viewable():
                text_widget.pack_forget()
                arrow_label.configure(text="\u25BC")
                container.configure(style="TFrame")
            else:
                text_widget.pack(fill="x", padx=15, pady=2)
                arrow_label.configure(text="\u25B2")
                container.configure(style="Open.TFrame")

        header.bind("<Button-1>", lambda e: toggle())
        title_label.bind("<Button-1>", lambda e: toggle())
        arrow_label.bind("<Button-1>", lambda e: toggle())

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

    # ----------------------- Test Execution ------------------------
    def start_test(self):
        if self.running:
            return
        os.makedirs(LOG_DIR, exist_ok=True)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        name = self.test_name_var.get() or "test"
        log_path = os.path.join(LOG_DIR, f"{timestamp}_{name}.log")
        self.log_file = open(log_path, "w")
        self.running = True
        self.paused = False
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.pause_btn.configure(state="normal", text="Pause")
        context = {}
        setup_code = self.setup_text.get("1.0", "end-1c")
        loop_code = self.script_text.get("1.0", "end-1c")
        def worker():
            with redirect_stdout(self.log_file):
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
