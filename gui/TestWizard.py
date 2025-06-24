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
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText

# Allow running from repo root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(REPO_ROOT, "config", "Test_Cell_Config.json")
LOG_DIR = os.path.join(REPO_ROOT, "logs")


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
    """Return list of (port, instance_name) tuples from config."""
    entries = []
    counts = {}
    for section in ("al1342", "al2205"):
        for port in sorted(cfg.get(section, {})):
            device = cfg.get(section, {}).get(port, "Empty")
            if device == "Empty":
                continue
            idx = counts.get(device, 0) + 1
            counts[device] = idx
            entries.append((port, f"{device}_{idx}"))
    return entries


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

        self.create_widgets()
        self.check_connection()

    # ----------------------- GUI Construction -----------------------
    def create_widgets(self):
        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=10, pady=10)

        # Style for highlighted open command boxes
        self.style = ttk.Style(self)
        self.style.configure("Open.TFrame", background="#e8f0fe")

        # Top frame with test name and device map
        header = ttk.Frame(main)
        header.pack(fill="x")

        name_frame = ttk.Frame(header)
        name_frame.pack(side="left", fill="x", expand=True)
        ttk.Label(name_frame, text="Test Name:").pack(side="left")
        self.test_name_var = tk.StringVar()
        ttk.Entry(name_frame, textvariable=self.test_name_var, width=30).pack(side="left", padx=5)

        if self.instance_map:
            map_frame = ttk.LabelFrame(header, text="Device Instances")
            map_frame.pack(side="right", padx=5)
            height = min(len(self.instance_map), 10) or 1
            self.map_list = tk.Listbox(map_frame, height=height, width=25)
            self.map_list.pack()
            for port, inst in self.instance_map:
                self.map_list.insert("end", f"{port}: {inst}")

        # Collapsible command library
        lib_frame = ttk.LabelFrame(main, text="Command Library")
        lib_frame.pack(fill="both", expand=False, pady=10)
        ttk.Label(lib_frame, text="Setup Commands").grid(row=0, column=0, sticky="w")
        ttk.Label(lib_frame, text="Test Commands").grid(row=0, column=1, sticky="w")

        setup_container = ttk.Frame(lib_frame)
        test_container = ttk.Frame(lib_frame)
        setup_container.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        test_container.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)

        for instr in self.library["setup"]:
            for title, content in self._parse_commands(instr, "Test Setup Commands"):
                self._create_collapsible_text(setup_container, title, content)

        for instr in self.library["test"]:
            for title, content in self._parse_commands(instr, "Test Commands"):
                self._create_collapsible_text(test_container, title, content)

        lib_frame.columnconfigure(0, weight=1)
        lib_frame.columnconfigure(1, weight=1)

        # Setup and script text boxes
        self.setup_text = ScrolledText(main, height=6)
        self.setup_text.pack(fill="both", expand=True, pady=(10, 5))
        self.setup_text.insert("end", "# Setup code\n")
        self.script_text = ScrolledText(main, height=8)
        self.script_text.pack(fill="both", expand=True)
        self.script_text.insert("end", "# Test loop code\n")

        # Buttons and status
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill="x", pady=10)
        self.start_btn = ttk.Button(btn_frame, text="Start", command=self.start_test)
        self.stop_btn = ttk.Button(btn_frame, text="Stop", command=self.stop_test, state="disabled")
        self.pause_btn = ttk.Button(btn_frame, text="Pause", command=self.toggle_pause, state="disabled")
        self.start_btn.pack(side="left", padx=5)
        self.stop_btn.pack(side="left", padx=5)
        self.pause_btn.pack(side="left", padx=5)
        self.status_var = tk.StringVar(value="Disconnected")
        self.status_label = ttk.Label(btn_frame, textvariable=self.status_var, foreground="red")
        self.status_label.pack(side="right")

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

        header = ttk.Frame(container)
        header.pack(fill="x")

        title_label = ttk.Label(header, text=section_title, font=("Arial", 10, "bold italic"))
        title_label.pack(side="left", padx=5, pady=(2, 0))

        arrow_label = ttk.Label(header, text="\u25BC")  # Down arrow
        arrow_label.pack(side="right", padx=5)

        text_widget = tk.Text(container, wrap="word", height=1, width=60,
                              font=("Arial", 9), background="#f5f5f5")
        text_widget.insert("1.0", content)

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

        text_widget.pack_forget()

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


if __name__ == "__main__":
    app = TestWizard()
    app.mainloop()
