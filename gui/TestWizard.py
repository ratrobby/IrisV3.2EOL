import os
import sys
import json
import time
import threading
import queue
import socket
import subprocess
import importlib
import importlib.util
import inspect
import types
from contextlib import redirect_stdout
import re
import traceback
import tempfile
import atexit

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText

from .calibration_wizard import CalibrationWizard
from IO_master import IO_master
from commands import Hold
from thread_utils import start_thread
from logger import CSVLogger, record_event

# Allow running from repo root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(REPO_ROOT, "config", "Test_Cell_Config.json")
DEFAULT_LOG_DIR = os.path.join(REPO_ROOT, "logs")
DEFAULT_TESTS_DIR = os.path.join(REPO_ROOT, "user_tests")

# Lock file used to ensure only one Test Wizard is running
LOCK_PATH = os.path.join(tempfile.gettempdir(), "mrlf_testwizard.lock")

# Ping timeout in seconds and interval for connection checks (ms)
PING_TIMEOUT = 0.25
CHECK_INTERVAL = 300


def _parse_command_title(title):
    """Return (name, [(param, default_or_None), ...]) from an instruction title."""
    match = re.match(r"\s*(\w+)\s*\((.*)\)", str(title))
    if not match:
        return title.strip(), []
    name = match.group(1)
    params = []
    inner = match.group(2).strip()
    if inner:
        for part in inner.split(','):
            part = part.strip()
            if not part:
                continue
            if '=' in part:
                p, default = part.split('=', 1)
                params.append((p.strip(), default.strip()))
            else:
                params.append((part, None))
    return name, params


def _acquire_lock():
    """Attempt to acquire the single instance lock."""
    lock_file = open(LOCK_PATH, "w")
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        lock_file.close()
        raise RuntimeError("Another Test Wizard is already running")
    return lock_file


def _release_lock(lock_file):
    """Release the single instance lock."""
    if not lock_file:
        return
    try:
        if os.name == "nt":
            import msvcrt
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock_file, fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        lock_file.close()
        os.unlink(LOCK_PATH)
    except Exception:
        pass


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
    """Return dict of test instructions from configured devices.

    The returned structure groups commands by device class name so the GUI can
    display them in labeled sections.
    """
    library = {"test": {}}
    modules = set()
    def _collect_modules(section):
        for mod in cfg.get(section, {}).values():
            if not mod:
                continue
            if str(mod).strip().lower() == "empty":
                continue
            yield str(mod).strip()

    modules.update(_collect_modules("al1342"))
    modules.update(_collect_modules("al2205"))

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

    # Add generic commands that are always available
    library["test"]["General"] = []

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
            device = str(device).strip()
            if device.lower() == "empty":
                continue
            device_totals[device] = device_totals.get(device, 0) + 1

    # Track numbering for devices that appear more than once
    counts = {}
    result = {"al1342": {}, "al2205": {}}
    for section in ("al1342", "al2205"):
        for port in sorted(cfg.get(section, {})):
            device = cfg.get(section, {}).get(port, "Empty")
            device = str(device).strip()
            if device.lower() == "empty":
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


def build_alias_class_map(cfg, instance_map):
    """Return mapping of device alias names to their class names."""
    alias_map = {"General": "General"}
    for section in ("al1342", "al2205"):
        for port, alias in instance_map.get(section, {}).items():
            dev_mod = str(cfg.get(section, {}).get(port, "")).strip()
            if not dev_mod or dev_mod.lower() == "empty":
                continue
            try:
                mod = importlib.import_module(f"devices.{dev_mod}")
            except Exception:
                continue
            device_cls = None
            for name, obj in inspect.getmembers(mod, inspect.isclass):
                if getattr(obj, "_is_device_class", False):
                    device_cls = obj
                    break
            if device_cls:
                alias_map[alias] = device_cls.__name__
    return alias_map


def load_device_objects(cfg, base_map, ip_address):
    """Import configured device instances using ``MRLF_TEST_SCRIPT``."""
    script = os.environ.get("MRLF_TEST_SCRIPT")
    if not script or not os.path.exists(script):
        return {}
    try:
        spec = importlib.util.spec_from_file_location("user_devices", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as e:
        print(f"Failed to load device objects: {e}")
        return {}

    try:
        master = IO_master(ip_address)
    except Exception as e:
        print(f"Failed to connect IO_master: {e}")
        return {}

    objects = {}
    classes = {}

    # Import required device classes
    for section in ("al1342", "al2205"):
        for dev_name in cfg.get(section, {}).values():
            if not dev_name:
                continue
            dev_name = str(dev_name).strip()
            if dev_name.lower() == "empty" or dev_name in classes:
                continue
            try:
                mod = importlib.import_module(f"devices.{dev_name}")
            except Exception as e:
                print(f"Failed to import device module '{dev_name}': {e}")
                continue
            device_cls = None
            for name, obj in inspect.getmembers(mod, inspect.isclass):
                if getattr(obj, "_is_device_class", False):
                    device_cls = obj
                    break
            if device_cls:
                classes[dev_name] = device_cls

    hub_obj = None

    # Instantiate AL1342 devices first
    for port in sorted(cfg.get("al1342", {})):
        dev_name = str(cfg["al1342"][port]).strip()
        if dev_name.lower() == "empty":
            continue
        cls = classes.get(dev_name)
        if not cls:
            continue
        port_num = int(port[1:]) if port.startswith("X") else int(port)
        inst_name = base_map["al1342"][port]
        try:
            obj = cls(master, port_number=port_num)
        except Exception as e:
            print(f"Failed to instantiate {dev_name}: {e}")
            continue
        objects[inst_name] = obj
        if dev_name == "AL2205_Hub":
            hub_obj = obj

    # Instantiate AL2205 devices connected to the hub
    if hub_obj:
        for port in sorted(cfg.get("al2205", {})):
            dev_name = str(cfg["al2205"][port]).strip()
            if dev_name.lower() == "empty":
                continue
            cls = classes.get(dev_name)
            if not cls:
                continue
            index = int(port.split(".")[-1])
            inst_name = base_map["al2205"][port]
            try:
                obj = cls(hub_obj, x1_index=index)
            except Exception as e:
                print(f"Failed to instantiate {dev_name}: {e}")
                continue
            objects[inst_name] = obj

    return objects


class TestMonitor(tk.Toplevel):
    """Simple window that displays test output."""

    def __init__(self, master):
        super().__init__(master)
        self.title("Test Monitor")
        self.geometry("600x400")
        self.text = ScrolledText(self, state="disabled")
        self.text.pack(fill="both", expand=True)

    def append(self, message):
        """Add a line of output with a timestamp.

        The monitor receives raw stdout data from the running test. This
        method prepends a ``HH:MM:SS`` timestamp to each non-empty line and
        filters out low level messages such as the register writes from the
        ``ValveBank`` class.
        """

        # Ignore purely whitespace updates
        msg = message.rstrip()
        if not msg:
            return

        # Skip verbose register write messages from ValveBank
        if msg.startswith("[ValveBank] Wrote"):
            return

        # Ignore lines about devices that are already off
        if "was not active" in msg:
            return

        timestamp = time.strftime("[%H:%M:%S] ")

        self.text.configure(state="normal")
        for line in msg.splitlines():
            if line.startswith("[ValveBank] Wrote") or not line.strip():
                continue
            if line.startswith("Iteration:"):
                self.text.insert("end", f"{line}\n")
            else:
                self.text.insert("end", f"{timestamp}{line}\n")
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
    def __init__(self, test_name=None, test_dir=None, load_path=None):
        super().__init__()
        self.title("Test Wizard")
        self.cfg = load_config()
        self.ip_address = self.cfg.get("ip_address", "192.168.XXX.XXX")
        self.library = gather_library(self.cfg)
        self.base_map = build_instance_map(self.cfg)
        self.instance_map = self.cfg.get("device_names") or {
            s: dict(p) for s, p in self.base_map.items()
        }
        self.alias_class_map = build_alias_class_map(self.cfg, self.instance_map)
        # Determine associated script and set environment variable
        self.test_script_path = os.environ.get("MRLF_TEST_SCRIPT")
        if self.test_script_path and not os.path.exists(self.test_script_path):
            self.test_script_path = None
        if self.test_script_path:
            os.environ["MRLF_TEST_SCRIPT"] = self.test_script_path
        else:
            os.environ.pop("MRLF_TEST_SCRIPT", None)

        # Holds instantiated device objects for calibration/setup widgets
        self.device_objects = load_device_objects(
            self.cfg, self.base_map, self.ip_address
        )
        self.setup_code = ""
        self.setup_values = {}

        self.running = False
        self.paused = False
        self.connection_lost = False
        self._last_connection_ok = True
        self.worker = None
        self.csv_logger = None
        self.log_file_path = None
        self.test_file_path = None
        self.monitor = None
        self.monitor_queue = queue.Queue()
        self.initial_test_name = test_name
        if load_path and not test_dir:
            test_dir = os.path.dirname(load_path)
        self.tests_dir = test_dir or DEFAULT_TESTS_DIR
        self.log_dir = self.tests_dir
        self._drag_row = None
        self._drag_index = None

        self.create_widgets()
        # Scale window after widgets have been laid out
        self.update_idletasks()
        # Position the window at x=100, y=50
        self.geometry("1600x950+150+20")
        # Ensure the wizard window is visible when launched
        self.deiconify()
        self.lift()
        try:
            self.focus_force()
        except Exception:
            pass
        self._stop_connection_monitor = threading.Event()
        self._connection_after_id = None
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.check_connection()
        self.after(100, self.poll_monitor_queue)
        self.after(100, self.poll_ui_button)
        if load_path:
            self.load_test(load_path)



    # ----------------------- GUI Construction -----------------------
    def create_widgets(self):
        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=10, pady=10)

        # Style for highlighted open command boxes
        self.style = ttk.Style(self)
        self.style.configure("Open.TFrame", background="#e8f0fe")
        self.style.configure("Drag.TFrame", background="#ffeeba")
        self.style.configure("TestName.TLabel", font=("Segoe UI Variable Display Semib", 12,))
        self.style.configure("DragHandle.TLabel", padding=3)

        # Main content split into left and right columns
        content = ttk.Frame(main)
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=1, uniform="cols")
        content.columnconfigure(1, weight=1, uniform="cols")
        content.rowconfigure(0, weight=1)

        # ----------------------- Left Column -----------------------
        left = ttk.Frame(content)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left.columnconfigure(0, weight=1)

        name_frame = ttk.Frame(left)
        name_frame.grid(row=0, column=0, sticky="ew")
        name_frame.columnconfigure(0, weight=1)

        ttk.Label(name_frame, text="Test Name:", style="TestName.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 5)
        )
        self.test_name_var = tk.StringVar(value=self.initial_test_name or "")
        if self.initial_test_name:
            ttk.Label(name_frame, text=self.initial_test_name, font=("Arial", 12)).grid(
                row=1, column=0, sticky="w", padx=5, pady=2
            )
        else:
            self.test_name_entry = ttk.Entry(
                name_frame, textvariable=self.test_name_var, font=("Arial", 12)
            )
            self.test_name_entry.grid(row=1, column=0, sticky="ew", padx=5, ipady=4)


        ttk.Label(left, text="Test Setup:", style="TestName.TLabel").grid(
            row=1, column=0, sticky="w", pady=(20, 0)
        )
        self.setup_frame = ttk.Frame(left)
        self.setup_frame.grid(row=2, column=0, sticky="nsew", pady=(5, 20))
        left.rowconfigure(2, weight=0)
        self.build_setup_widgets()

        ttk.Label(left, text="Test Loop:", style="TestName.TLabel").grid(
            row=3, column=0, sticky="w"
        )
        self.loop_frame = ttk.Frame(left)
        self.loop_frame.grid(row=4, column=0, sticky="nsew", pady=(5, 0))
        left.rowconfigure(4, weight=1)

        btn_row = ttk.Frame(self.loop_frame)
        btn_row.pack(anchor="w")
        ttk.Button(btn_row, text="Add Section", command=self.add_section).pack(
            side="left", padx=5, pady=2
        )

        # Scrollable container for loop sections
        self.rows_canvas = tk.Canvas(self.loop_frame, highlightthickness=0)
        self.rows_scroll = ttk.Scrollbar(
            self.loop_frame, orient="vertical", command=self.rows_canvas.yview
        )
        self.rows_canvas.configure(yscrollcommand=self.rows_scroll.set)
        self.rows_scroll.pack(side="right", fill="y")
        self.rows_canvas.pack(side="left", fill="both", expand=True)

        # Allow scrolling the loop builder with the mouse wheel
        self.rows_canvas.bind("<Enter>", self._bind_loop_scroll)
        self.rows_canvas.bind("<Leave>", self._unbind_loop_scroll)

        self.rows_container = ttk.Frame(self.rows_canvas)
        self.rows_window = self.rows_canvas.create_window(
            (0, 0), window=self.rows_container, anchor="nw"
        )

        def _on_frame_configure(event):
            self.rows_canvas.configure(
                scrollregion=self.rows_canvas.bbox("all")
            )

        def _on_canvas_configure(event):
            self.rows_canvas.itemconfigure(
                self.rows_window, width=event.width
            )

        self.rows_container.bind("<Configure>", _on_frame_configure)
        self.rows_canvas.bind("<Configure>", _on_canvas_configure)

        self.loop_sections = []

        # Start with one empty section
        self.after(10, self.add_section)


        ttk.Label(left, text="Iterations:", style="TestName.TLabel").grid(
            row=5, column=0, sticky="w", pady=(10, 0)
        )
        self.iterations_var = tk.StringVar()
        self.iterations_entry = ttk.Entry(left, textvariable=self.iterations_var)
        self.iterations_entry.grid(row=6, column=0, sticky="w", padx=5, pady=(0, 10))

        btn_frame = ttk.Frame(left)
        btn_frame.grid(row=7, column=0, sticky="w", padx=5, pady=(0, 10))
        self.run_btn = ttk.Button(btn_frame, text="Run Script", command=self.run_script)
        self.run_btn.pack(side="left")
        self.step_btn = ttk.Button(
            btn_frame, text="\u23E5 Step", command=self.step_script, state="disabled"
        )
        self.step_btn.pack(side="left", padx=5)

        # ----------------------- Right Column ----------------------
        right = ttk.Frame(content)
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        right.columnconfigure(0, weight=1)

        inst_status = ttk.Frame(right)
        inst_status.pack(fill="x", padx=5, pady=(0, 5))
        # Give the device mapping display more space than the connection status
        inst_status.columnconfigure(0, weight=3)
        inst_status.columnconfigure(1, weight=1)
        inst_status.rowconfigure(0, weight=1)
        inst_status.rowconfigure(1, weight=1)

        self.map_frame = None
        if self.instance_map:
            self.map_frame = ttk.LabelFrame(inst_status, text="Device Instances")
            self.map_frame.grid(row=0, column=0, sticky="nsew")
            self.refresh_instance_table()

        status_frame = ttk.LabelFrame(inst_status, text="AL1342 Connection Status:")
        status_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        # Narrower status frame to emphasize the device mapping table
        status_frame.configure(width=150)
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

        # Refresh button allows the user to reload device objects if the wizard
        # was launched while the AL1342 was disconnected.
        self.refresh_btn = ttk.Button(
            status_frame, text="Refresh", command=self.refresh_wizard
        )
        self.refresh_btn.pack(fill="x", padx=5, pady=(0, 5))

        # Collapsible command library below the device instances
        lib_container, lib_frame = self._create_collapsible_section(
            right, "Command Library"
        )
        lib_container.pack(fill="both", expand=True, padx=5, pady=5)
        # With the command library open by default, let it claim the
        # available space rather than the test loop editor.
        self.lib_container = lib_container
        lib_frame.columnconfigure(0, weight=1)

        test_label = ttk.Label(
            lib_frame, text="Test Commands", font=("Arial", 11, "underline")
        )
        self.test_container = ttk.LabelFrame(lib_frame, labelwidget=test_label)
        self.test_container.pack(fill="both", expand=True, padx=5, pady=(0, 5))
        self.populate_command_library()

        # The lower test editor has been removed to avoid duplication. The
        # primary test loop editor remains in the left column above.

        # Editor showing the generated test script will appear below the
        # command library but above the test control buttons
        self.script_text = ScrolledText(right, height=6)
        self.script_text.pack(fill="both", expand=True, padx=5, pady=(0, 5))
        self.script_text.insert("end", "# Test loop code\n")
        # When the command library is visible, keep the script text from
        # expanding so the library gets most of the vertical space.
        self.script_text.pack_configure(expand=False)

        # Test control buttons anchored at the bottom of the window
        control_frame = ttk.LabelFrame(right, text="Test Control Panel")
        control_frame.pack(fill="x", padx=5, pady=(5, 5))

        self.style.configure("Start.TButton", foreground="green", font=("Arial", 20))
        self.style.configure("Stop.TButton", foreground="red", font=("Arial", 20))
        self.style.configure("Pause.TButton", foreground="blue", font=("Arial", 20))
        self.style.configure("Resume.TButton", foreground="blue", font=("Arial", 20))

        self.start_btn = ttk.Button(
            control_frame,
            text="\u25CF Start Test",
            command=self.start_test,
            style="Start.TButton",
        )
        self.stop_btn = ttk.Button(
            control_frame,
            text="\u25A0 Stop Test",
            command=lambda: self.stop_test(prompt=True),
            state="disabled",
            style="Stop.TButton",
        )
        self.pause_btn = ttk.Button(
            control_frame,
            text="\u23F8 Pause Test",
            command=self.pause_test,
            state="disabled",
            style="Pause.TButton",
        )
        self.resume_btn = ttk.Button(
            control_frame,
            text="\u25B6 Resume Test",
            command=self.resume_test,
            state="disabled",
            style="Resume.TButton",
        )
        self.step_mode_var = tk.BooleanVar()
        self.step_mode_check = ttk.Checkbutton(
            control_frame, text="Step Mode", variable=self.step_mode_var
        )
        self.step_event = None
        self.start_btn.pack(side="left", padx=5)
        self.stop_btn.pack(side="left", padx=5)
        self.pause_btn.pack(side="left", padx=5)
        self.resume_btn.pack(side="left", padx=5)
        self.step_mode_check.pack(side="left", padx=5)

        # Buttons related to file handling
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill="x", pady=10)

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

    def _create_collapsible_section(self, parent, title):
        """Return (container, content_frame) for a collapsible section."""
        container = ttk.Frame(parent)

        header = ttk.Frame(container)
        header.pack(fill="x")

        arrow = ttk.Label(header, text="\u25BC")
        arrow.pack(side="left", padx=5)

        label = ttk.Label(header, text=title, font=("Arial", 12, "bold"))
        label.pack(side="left")

        content = ttk.Frame(container)
        content.pack(fill="both", expand=True)

        def toggle():
            if content.winfo_viewable():
                content.forget()
                arrow.configure(text="\u25B6")
                container.pack_configure(expand=False)
                if hasattr(self, "script_text"):
                    self.script_text.pack_configure(expand=True)
            else:
                content.pack(fill="both", expand=True)
                arrow.configure(text="\u25BC")
                container.pack_configure(expand=True)
                if hasattr(self, "script_text"):
                    self.script_text.pack_configure(expand=False)

        for w in (header, label, arrow):
            w.bind("<Button-1>", lambda e: toggle())

        return container, content

    def populate_command_library(self):
        """Rebuild the command library UI from ``self.library``."""
        if not getattr(self, "test_container", None):
            return
        for child in self.test_container.winfo_children():
            child.destroy()
        for device, cmds in self.library.get("test", {}).items():
            ttk.Label(self.test_container, text=device, font=("Arial", 10, "bold")).pack(anchor="w", pady=0)
            dev_frame = ttk.Frame(self.test_container)
            dev_frame.pack(fill="x", padx=10, pady=(0, 2))
            for cmd in cmds:
                self._create_collapsible_text(dev_frame, cmd.get("title"), cmd.get("content"))

    def build_setup_widgets(self):
        """Populate the setup frame with device-specific widgets."""
        for w in self.setup_frame.winfo_children():
            w.destroy()
        class_seen = set()
        devices = []
        for section in ("al1342", "al2205"):
            for port in sorted(self.instance_map.get(section, {})):
                alias = self.instance_map[section][port]
                base = self.base_map[section][port]
                obj = getattr(self, "device_objects", {}).get(base)
                if not obj:
                    continue
                devices.append((alias, obj))

        def _sort_key(item):
            alias, obj = item
            cls_name = obj.__class__.__name__
            if cls_name == "ValveBank":
                return (0, 0)
            if cls_name == "PressureRegulatorITV1050":
                m = re.search(r"_(\d+)$", alias)
                idx = int(m.group(1)) if m else 0
                return (1, idx)
            return (2, cls_name, alias)

        for alias, obj in sorted(devices, key=_sort_key):
            cls = obj.__class__
            if cls.__name__ == "LoadCellLCM300" and cls not in class_seen:
                ttk.Button(
                    self.setup_frame,
                    text="Calibrate Load Cells",
                    command=self.open_loadcell_calibration,
                ).pack(fill="x", padx=5, pady=2)
                class_seen.add(cls)
            elif cls.__name__ == "PositionSensorSDATMHS_M160" and cls not in class_seen:
                ttk.Button(
                    self.setup_frame,
                    text="Calibrate Position Sensors",
                    command=self.open_position_sensor_calibration,
                ).pack(fill="x", padx=5, pady=2)
                class_seen.add(cls)

            saved = self.setup_values.get(alias)
            if saved is not None and hasattr(obj, "load_setup_state"):
                try:
                    obj.load_setup_state(saved)
                except Exception as e:
                    print(f"Failed to apply setup state for {alias}: {e}")

            if hasattr(obj, "setup_widget"):
                try:
                    widget = obj.setup_widget(
                        self.setup_frame,
                        name=alias,
                        on_update=lambda v, a=alias: self._update_setup_value(a, v),
                    )
                    if widget:
                        widget.pack(fill="x", padx=5, pady=2)
                except Exception as e:
                    print(f"Failed to build setup widget for {alias}: {e}")

    def _update_setup_value(self, alias, value):
        """Store the latest setup value for a device alias."""
        self.setup_values[alias] = value

    def _collect_setup_values(self):
        """Gather current setup values from all devices."""
        values = {}
        for section in ("al1342", "al2205"):
            for port in self.instance_map.get(section, {}):
                alias = self.instance_map[section][port]
                base = self.base_map[section][port]
                obj = getattr(self, "device_objects", {}).get(base)
                if obj and hasattr(obj, "get_setup_state"):
                    try:
                        val = obj.get_setup_state()
                    except Exception:
                        val = None
                    if val is not None:
                        values[alias] = val
        return values

    def _serialize_loop_builder(self):
        """Return a serializable representation of the loop builder."""
        sections = []
        for sec in getattr(self, "loop_sections", []):
            steps = []
            for row in sec.loop_rows:
                params = {
                    name: var.get().strip()
                    for name, var, _ in getattr(row, "param_vars", [])
                }
                steps.append(
                    {
                        "device": row.device_var.get(),
                        "command": row.command_var.get(),
                        "params": params,
                        "thread": bool(
                            getattr(row, "thread_var", None)
                            and row.thread_var.get()
                        ),
                        "hold": (
                            getattr(row, "hold_var", None).get().strip()
                            if getattr(row, "hold_var", None)
                            else ""
                        ),
                    }
                )
            sections.append({"name": sec.name_var.get().strip(), "steps": steps})
        return {"step_mode": bool(self.step_mode_var.get()), "sections": sections}

    def _load_loop_builder(self, builder):
        """Rebuild loop sections and rows from serialized ``builder`` data."""
        sections = builder.get("sections", []) if isinstance(builder, dict) else builder
        for sec in sections:
            section = self.add_section(add_row=False)
            section.name_var.set(sec.get("name", ""))
            for step in sec.get("steps", []):
                self.add_loop_row(section)
                row = section.loop_rows[-1]
                row.device_var.set(step.get("device", "General"))
                self._update_row_commands(row)
                row.command_var.set(step.get("command", ""))
                self._build_param_fields(row)
                params = step.get("params", {})
                for name, var, _ in getattr(row, "param_vars", []):
                    if name in params:
                        var.set(params.get(name, ""))
                if step.get("thread") and getattr(row, "thread_var", None):
                    row.thread_var.set(True)
                hold_val = step.get("hold")
                if hold_val is not None and getattr(row, "hold_var", None):
                    row.hold_var.set(str(hold_val))
        if isinstance(builder, dict):
            self.step_mode_var.set(bool(builder.get("step_mode")))
        self.update_loop_script()

    def refresh_instance_table(self):
        """Update the Device Instances table with current names."""
        if not getattr(self, "map_frame", None):
            return
        for child in self.map_frame.winfo_children():
            child.destroy()

        self.map_frame.columnconfigure(0, weight=1)
        self.map_frame.columnconfigure(1, weight=1)

        label1 = ttk.Label(self.map_frame, text="AL1342", font=("Arial", 10, "underline"))
        label2 = ttk.Label(self.map_frame, text="AL2205", font=("Arial", 10, "underline"))

        col1 = ttk.LabelFrame(self.map_frame, labelwidget=label1)
        col2 = ttk.LabelFrame(self.map_frame, labelwidget=label2)
        col1.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=2)
        col2.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=2)

        col1.columnconfigure(1, weight=1)
        col2.columnconfigure(1, weight=1)

        for r, port in enumerate(sorted(self.instance_map.get("al1342", {})), start=1):
            ttk.Label(col1, text=f"{port}:").grid(row=r, column=0, sticky="e", pady=1)
            val = self.instance_map["al1342"][port]
            ttk.Label(col1, text=val).grid(row=r, column=1, sticky="w")

        for r, port in enumerate(sorted(self.instance_map.get("al2205", {})), start=1):
            ttk.Label(col2, text=f"{port}:").grid(row=r, column=0, sticky="e", pady=1)
            val = self.instance_map["al2205"][port]
            ttk.Label(col2, text=val).grid(row=r, column=1, sticky="w")

    def open_calibration(self, device):
        """Launch the generic calibration wizard for a device."""
        if self.test_script_path and os.path.exists(self.test_script_path):
            os.environ["MRLF_TEST_SCRIPT"] = self.test_script_path
        else:
            os.environ.pop("MRLF_TEST_SCRIPT", None)
        try:
            steps = device.__class__.calibration_steps()
        except Exception as e:
            print(f"Failed to load calibration steps: {e}")
            return
        if not steps:
            return
        CalibrationWizard(device, steps)

    def open_loadcell_calibration(self):
        from devices.LoadCell_LCM300 import Calibrate_LoadCell_Zero
        Calibrate_LoadCell_Zero()

    def open_position_sensor_calibration(self):
        from devices.PositionSensor_SDAT_MHS_M160 import Calibrate_PosSensor
        Calibrate_PosSensor()


    def _export_device_alias_script(self, test_name):
        """Write ``<test_name>_Script.py`` containing only device aliases."""
        safe = re.sub(r"\W+", "_", test_name)
        script_path = os.path.join(self.tests_dir, f"{safe}_Script.py")

        from . import utils
        cfg = dict(self.cfg)
        cfg["device_names"] = self.instance_map
        base_content = utils.export_device_setup(cfg)

        alias_lines = []

        script_parts = [
            base_content,
            "\n".join(alias_lines),
            "",
        ]

        os.makedirs(self.tests_dir, exist_ok=True)
        with open(script_path, "w") as fh:
            fh.write("\n".join(script_parts))
        return script_path

    def reset_device_names(self):
        """Revert device instance names to defaults from the configuration."""
        self.instance_map = {s: dict(p) for s, p in self.base_map.items()}
        self.alias_class_map = build_alias_class_map(self.cfg, self.instance_map)
        self.refresh_instance_table()

    def refresh_wizard(self):
        """Reload device objects and rebuild setup widgets."""
        self.device_objects = load_device_objects(
            self.cfg, self.base_map, self.ip_address
        )
        self.build_setup_widgets()
        self.alias_class_map = build_alias_class_map(self.cfg, self.instance_map)
        self.refresh_instance_table()

    # ----------------------- Loop Builder ------------------------
    def _get_all_commands(self):
        cmds = {}
        for dev_cmds in self.library.get("test", {}).values():
            for item in dev_cmds:
                title = item.get("title")
                if not title or "(" not in title:
                    continue
                name, params = _parse_command_title(title)
                cmds[name] = params
        return cmds

    def _get_all_devices(self):
        names = []
        for section in ("al1342", "al2205"):
            for port in self.instance_map.get(section, {}):
                alias = self.instance_map[section][port]
                if alias and alias != "Empty" and alias not in names:
                    names.append(alias)
        return sorted(names, key=str.lower)

    def _get_device_commands(self, alias):
        class_name = self.alias_class_map.get(alias)
        if not class_name:
            return {}
        cmds = {}
        for item in self.library.get("test", {}).get(class_name, []):
            title = item.get("title")
            if not title or "(" not in title:
                continue
            name, params = _parse_command_title(title)
            cmds[name] = params
        return cmds

    def _update_row_commands(self, row):
        cmds = list(self._get_device_commands(row.device_var.get()).keys())
        row.command_cb.configure(values=cmds)
        if row.command_var.get() not in cmds:
            row.command_var.set(cmds[0] if cmds else "")
        self._build_param_fields(row)

    def add_section(self, add_row=True):
        section = ttk.Frame(self.rows_container)
        section.pack(fill="x", pady=5)

        # Header with section name and controls
        header = ttk.Frame(section)
        header.pack(fill="x")

        section.expanded = tk.BooleanVar(value=True)
        section.name_var = tk.StringVar(value="Section")

        def toggle():
            if section.expanded.get():
                section.rows_container.forget()
                section.expanded.set(False)
                expand_btn.configure(text="\u25BA")
            else:
                section.rows_container.pack(fill="x")
                section.expanded.set(True)
                expand_btn.configure(text="\u25BC")

        expand_btn = ttk.Button(header, text="\u25BC", width=2, command=toggle)
        expand_btn.pack(side="left")

        name_entry = ttk.Entry(header, textvariable=section.name_var, width=20)
        name_entry.pack(side="left", padx=5)
        name_entry.bind("<KeyRelease>", lambda e: self.update_loop_script())

        ttk.Button(
            header,
            text="Add Step",
            command=lambda s=section: self.add_loop_row(s),
        ).pack(side="left", padx=5)

        ttk.Button(
            header,
            text="Duplicate",
            command=lambda s=section: self._duplicate_section(s),
        ).pack(side="right", padx=5)

        ttk.Button(
            header,
            text="Remove",
            command=lambda s=section: self._remove_section(s),
        ).pack(side="right", padx=5)

        # Bind drag events for reordering sections
        header.bind("<ButtonPress-1>", lambda e, s=section: self._start_section_drag(e, s))
        header.bind("<B1-Motion>", lambda e, s=section: self._on_section_drag(e, s))
        header.bind("<ButtonRelease-1>", lambda e, s=section: self._end_section_drag(e, s))

        section.rows_container = ttk.Frame(section)
        section.rows_container.pack(fill="x")

        section.loop_rows = []

        self.loop_sections.append(section)
        if add_row:
            self.add_loop_row(section)
        return section

    def add_loop_row(self, section=None):
        if section is None:
            if not self.loop_sections:
                section = self.add_section()
            else:
                section = self.loop_sections[-1]
        commands = list(self._get_device_commands("General").keys())
        row = ttk.Frame(section.rows_container)
        row.pack(fill="x", pady=2)

        row.top_frame = ttk.Frame(row)
        row.top_frame.pack(fill="x")

        # Drag handle for reordering rows
        handle = ttk.Label(row.top_frame, text="\u2630", cursor="hand2", style="DragHandle.TLabel")
        handle.pack(side="left", padx=(0, 5))
        handle.bind("<ButtonPress-1>", lambda e, r=row: self._start_row_drag(e, r))
        handle.bind("<B1-Motion>", lambda e, r=row: self._on_row_drag(e, r))
        handle.bind("<ButtonRelease-1>", lambda e, r=row: self._end_row_drag(e, r))
        row.drag_handle = handle

        devices = ["General"] + self._get_all_devices()

        row.device_var = tk.StringVar()
        dev_cb = ttk.Combobox(
            row.top_frame,
            textvariable=row.device_var,
            values=devices,
            state="readonly",
            width=18,
        )
        dev_cb.pack(side="left", padx=5)
        dev_cb.bind(
            "<<ComboboxSelected>>",
            lambda e, r=row: (self._update_row_commands(r), self.update_loop_script()),
        )
        row.device_var.set(devices[0] if devices else "")

        row.command_var = tk.StringVar()
        cb = ttk.Combobox(
            row.top_frame,
            textvariable=row.command_var,
            values=commands,
            state="readonly",
            width=20,
        )
        cb.pack(side="left", padx=5)
        row.command_cb = cb

        row.param_frame = ttk.Frame(row.top_frame)
        row.param_frame.pack(side="left", fill="x", expand=True)

        dup_btn = ttk.Button(
            row.top_frame,
            text="Duplicate",
            command=lambda r=row: self._duplicate_loop_row(r),
        )
        dup_btn.pack(side="right", padx=5)

        row.thread_var = tk.BooleanVar()
        thread_chk = ttk.Checkbutton(
            row.top_frame,
            text="Thread",
            variable=row.thread_var,
            command=self.update_loop_script,
        )
        thread_chk.pack(side="right", padx=5)

        del_btn = ttk.Button(
            row.top_frame,
            text="Remove",
            command=lambda r=row: self._remove_loop_row(r),
        )
        del_btn.pack(side="right", padx=5)

        def on_select(event=None, r=row):
            self._build_param_fields(r)
            self.update_loop_script()

        cb.bind("<<ComboboxSelected>>", on_select)
        row.command_var.set(commands[0] if commands else "")

        row.hold_var = tk.StringVar(value="0")
        row.hold_frame = ttk.Frame(row)
        row.hold_frame.pack(fill="x", padx=5, pady=(2, 0))
        ttk.Label(row.hold_frame, text="Hold After (s):").pack(side="left")
        hold_entry = ttk.Entry(row.hold_frame, textvariable=row.hold_var, width=10)
        hold_entry.pack(side="left")
        hold_entry.bind("<KeyRelease>", lambda e: self.update_loop_script())

        section.loop_rows.append(row)
        row.section = section
        self._update_row_commands(row)
        on_select()



    def _remove_loop_row(self, row):
        if hasattr(row, "section") and row in row.section.loop_rows:
            row.section.loop_rows.remove(row)
        row.destroy()
        # Defer script update slightly so the UI has time to remove the row
        try:
            self.after(10, self.update_loop_script)
        except Exception:
            self.update_loop_script()

    def _duplicate_loop_row(self, row):
        """Create a duplicate of ``row`` at the bottom of its section."""
        section = getattr(row, "section", None)
        if section is None:
            return
        device = row.device_var.get()
        command = row.command_var.get()
        values = [var.get() for _, var, _ in getattr(row, "param_vars", [])]

        self.add_loop_row(section)
        new_row = section.loop_rows[-1]
        new_row.device_var.set(device)
        self._update_row_commands(new_row)
        new_row.command_var.set(command)
        self._build_param_fields(new_row)

        new_row.hold_var.set(row.hold_var.get())

        for val, (_, var, _) in zip(values, getattr(new_row, "param_vars", [])):
            var.set(val)

        self.update_loop_script()

    def _bind_drag_events(self, widget, row):
        """Recursively bind drag events for the given row."""
        widget.bind("<ButtonPress-1>", lambda e, r=row: self._start_row_drag(e, r), add="+")
        widget.bind("<B1-Motion>", lambda e, r=row: self._on_row_drag(e, r), add="+")
        widget.bind("<ButtonRelease-1>", lambda e, r=row: self._end_row_drag(e, r), add="+")
        for child in widget.winfo_children():
            self._bind_drag_events(child, row)

    def _start_row_drag(self, event, row):
        """Begin dragging the given row."""
        self._drag_row = row
        self._drag_index = row.section.loop_rows.index(row)
        row.configure(style="Drag.TFrame")

    def _on_row_drag(self, event, row):
        """Reorder rows as the mouse moves during a drag."""
        if getattr(self, "_drag_row", None) is not row:
            return
        y = event.y_root - row.section.rows_container.winfo_rooty()
        target = None
        for r in row.section.loop_rows:
            if r is row:
                continue
            mid = r.winfo_y() + r.winfo_height() // 2
            if y < mid:
                target = r
                break
        row.pack_forget()
        if target:
            row.pack(before=target, fill="x", pady=2)
        else:
            # If row was last or no target found, pack at the end
            row.pack(fill="x", pady=2)

    def _end_row_drag(self, event, row):
        """Finalize row drag and update internal ordering."""
        if getattr(self, "_drag_row", None) is not row:
            return
        row.configure(style="TFrame")
        self._drag_row = None
        self._drag_index = None
        row.section.loop_rows.sort(key=lambda r: r.winfo_y())
        self.update_loop_script()

    # ----------------------- Section Management -----------------
    def _remove_section(self, section):
        if section in self.loop_sections:
            self.loop_sections.remove(section)
        for r in section.loop_rows:
            r.destroy()
        section.destroy()
        self.update_loop_script()

    def _duplicate_section(self, section):
        if section not in self.loop_sections:
            return
        idx = self.loop_sections.index(section)
        new_sec = self.add_section(add_row=False)
        new_sec.name_var.set(section.name_var.get())
        for row in section.loop_rows:
            self.add_loop_row(new_sec)
            new_row = new_sec.loop_rows[-1]
            new_row.device_var.set(row.device_var.get())
            self._update_row_commands(new_row)
            new_row.command_var.set(row.command_var.get())
            self._build_param_fields(new_row)
            for val, (_, var, _) in zip(
                [v.get() for _, v, _ in row.param_vars], new_row.param_vars
            ):
                var.set(val)
            if row.thread_var.get():
                new_row.thread_var.set(True)
        new_sec.pack(after=section, fill="x", pady=5)
        self.loop_sections.insert(idx + 1, self.loop_sections.pop(-1))
        self.update_loop_script()

    def _start_section_drag(self, event, section):
        self._drag_section = section
        section.configure(style="Drag.TFrame")

    def _on_section_drag(self, event, section):
        if getattr(self, "_drag_section", None) is not section:
            return
        y = event.y_root - self.rows_container.winfo_rooty()
        target = None
        for s in self.loop_sections:
            if s is section:
                continue
            mid = s.winfo_y() + s.winfo_height() // 2
            if y < mid:
                target = s
                break
        section.pack_forget()
        if target:
            section.pack(before=target, fill="x", pady=5)
        else:
            section.pack(after=self.loop_sections[-1], fill="x", pady=5)

    def _end_section_drag(self, event, section):
        if getattr(self, "_drag_section", None) is not section:
            return
        section.configure(style="TFrame")
        self._drag_section = None
        self.loop_sections.sort(key=lambda s: s.winfo_y())
        self.update_loop_script()

    # ----------------------- Mouse Wheel Scrolling ----------------
    def _bind_loop_scroll(self, event=None):
        """Enable mouse wheel scrolling for the loop builder."""
        if not getattr(self, "rows_canvas", None):
            return
        self.rows_canvas.bind_all("<MouseWheel>", self._on_loop_mousewheel)
        self.rows_canvas.bind_all("<Button-4>", self._on_loop_mousewheel)
        self.rows_canvas.bind_all("<Button-5>", self._on_loop_mousewheel)

    def _unbind_loop_scroll(self, event=None):
        """Disable mouse wheel scrolling for the loop builder."""
        if not getattr(self, "rows_canvas", None):
            return
        self.rows_canvas.unbind_all("<MouseWheel>")
        self.rows_canvas.unbind_all("<Button-4>")
        self.rows_canvas.unbind_all("<Button-5>")

    def _on_loop_mousewheel(self, event):
        """Scroll the loop builder canvas when the mouse wheel is used."""
        if event.delta:
            self.rows_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        elif event.num == 4:
            self.rows_canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.rows_canvas.yview_scroll(1, "units")

    def _build_param_fields(self, row):
        for child in row.param_frame.winfo_children():
            child.destroy()
        cmd = row.command_var.get()
        params = self._get_device_commands(row.device_var.get()).get(cmd, [])
        row.param_vars = []
        for name, default in params:
            frm = ttk.Frame(row.param_frame)
            frm.pack(side="left", padx=2)
            ttk.Label(frm, text=f"{name}:").pack(side="left")
            var = tk.StringVar()
            if default is not None:
                var.set(default)
            ent = ttk.Entry(frm, textvariable=var, width=10)
            ent.pack(side="left")
            ent.bind("<KeyRelease>", lambda e: self.update_loop_script())
            row.param_vars.append((name, var, default))

    def update_loop_script(self):
        lines = []
        for section in getattr(self, "loop_sections", []):
            sec_name = section.name_var.get().strip()
            if sec_name:
                lines.append(f"# {sec_name}")
            for row in section.loop_rows:
                cmd = row.command_var.get()
                args = []
                for name, var, default in getattr(row, "param_vars", []):
                    val = var.get().strip()
                    if val:
                        arg = val
                        base_name = name.lstrip("*").lower()
                        if base_name in {"unit", "valve", "valves"}:
                            if base_name == "valves" and "," in arg:
                                parts = [p.strip() for p in arg.split(',') if p.strip()]
                                quoted = []
                                for p in parts:
                                    if not (p.startswith('"') and p.endswith('"')):
                                        p = f'"{p}"'
                                    quoted.append(p)
                                arg = ", ".join(quoted)
                            else:
                                if not (arg.startswith('"') and arg.endswith('"')):
                                    arg = f'"{arg}"'
                        if default is not None:
                            args.append(f"{name}={arg}")
                        else:
                            args.append(arg)
                    elif default is not None:
                        args.append(f"{name}={default}")
                    else:
                        args.append("None")
                device = getattr(row, "device_var", None)
                dev = device.get().strip() if device else ""
                line = (
                    f"{dev}.{cmd}({', '.join(args)})" if dev and dev != "General" else f"{cmd}({', '.join(args)})"
                )
                if getattr(row, "thread_var", None) and row.thread_var.get():
                    line = f"start_thread(lambda: {line})"
                lines.append(line)
                hold_val = getattr(row, "hold_var", None)
                if hold_val:
                    hv = hold_val.get().strip()
                    if hv and hv != "0":
                        lines.append(f"Hold({hv})")
        self.script_text.delete("1.0", "end")
        self.script_text.insert("1.0", "# Test loop code\n" + "\n".join(lines))

    # ----------------------- Connection Status ---------------------
    def check_connection(self):
        """Check AL1342 connectivity in a background thread and update the UI."""

        def ping():
            try:
                sock = socket.create_connection(
                    (self.ip_address, 502), timeout=PING_TIMEOUT
                )
                sock.close()
                ok = True
            except Exception:
                ok = False

            def update():
                self.status_var.set("Connected" if ok else "Disconnected")
                self.status_label.configure(foreground="green" if ok else "red")
                if not ok and self.running and not self.paused:
                    # Automatically pause the test on connection loss
                    self.pause_test()
                    self.connection_lost = True
                self._last_connection_ok = ok
                if not self._stop_connection_monitor.is_set():
                    self._connection_after_id = self.after(CHECK_INTERVAL, self.check_connection)

            self.after(0, update)

        if not self._stop_connection_monitor.is_set():
            threading.Thread(target=ping, daemon=True).start()

    def poll_monitor_queue(self):
        while not self.monitor_queue.empty():
            msg = self.monitor_queue.get()
            if self.monitor and self.monitor.winfo_exists():
                self.monitor.append(msg)
        self.after(100, self.poll_monitor_queue)

    def poll_ui_button(self):
        """Check the hardware UI button and pause/resume if needed."""
        button = self.device_objects.get("UI_Button")
        if button:
            try:
                val = button.read_button()
            except Exception:
                val = None

            if val == 0 and self.running and not self.paused:
                self.pause_test()
            elif val == 257 and self.running and self.paused:
                self.resume_test()

        self.after(100, self.poll_ui_button)

    def _set_edit_state(self, state):
        """Enable or disable editing widgets based on state."""
        if hasattr(self, "test_name_entry"):
            self.test_name_entry.configure(state=state)
        for child in self.setup_frame.winfo_children():
            try:
                child.configure(state=state)
            except Exception:
                pass
        self.script_text.configure(state=state)
        for section in getattr(self, "loop_sections", []):
            for row in section.loop_rows:
                for widget in row.winfo_children():
                    try:
                        widget.configure(state=state)
                    except Exception:
                        pass
        self.iterations_entry.configure(state=state)
        self.save_btn.configure(state=state)
        self.new_btn.configure(state=state)
        self.reconfig_btn.configure(state=state)

    # ----------------------- Test Execution ------------------------
    def run_script(self, step=False):
        """Execute the test loop once without logging results."""
        # Ensure device objects are available by exporting the alias script if
        # it does not already exist. This mirrors the behaviour of
        # ``start_test`` which always saves the test before running.
        if not self.test_script_path or not os.path.exists(self.test_script_path):
            self.save_test(show_message=False)
        if self.test_script_path and os.path.exists(self.test_script_path):
            os.environ["MRLF_TEST_SCRIPT"] = self.test_script_path
        else:
            os.environ.pop("MRLF_TEST_SCRIPT", None)

        context = {"__name__": "__main__"}
        try:
            if self.test_script_path and os.path.exists(self.test_script_path):
                spec = importlib.util.spec_from_file_location(
                    "user_devices", self.test_script_path
                )
                devices_mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(devices_mod)
            else:
                devices_mod = types.ModuleType("user_devices")
        except Exception as e:
            print(f"Failed to load device objects: {e}")
            devices_mod = types.SimpleNamespace()

        for name, obj in getattr(devices_mod, "__dict__", {}).items():
            if not name.startswith("_"):
                context[name] = obj
        for section in ("al1342", "al2205"):
            for port in self.instance_map.get(section, {}):
                alias = self.instance_map[section][port]
                base = self.base_map[section][port]
                if alias != base and base in context:
                    context[alias] = context[base]

        # Add utilities for pausing and threading commands
        context["Hold"] = Hold
        context["start_thread"] = start_thread

        setup_code = self.setup_code
        loop_code = self.script_text.get("1.0", "end-1c")
        if not self.monitor or not self.monitor.winfo_exists():
            self.monitor = TestMonitor(self)
        else:
            self.monitor.deiconify()
            self.monitor.lift()
        queue_writer = _QueueWriter(self.monitor_queue)
        if step:
            self.step_event = threading.Event()
            self.step_btn.configure(state="normal")
            self._step_script_active = True
        else:
            self.step_event = None
            self.step_btn.configure(state="disabled")

        def worker():
            with redirect_stdout(_Tee(queue_writer)):
                try:
                    exec(setup_code, context)
                except Exception as e:
                    print(f"Setup error: {e}")
                    return
                try:
                    print("Iteration: 1")
                    lines = [ln for ln in loop_code.splitlines() if ln.strip()]
                    for ln in lines:
                        if self.step_event:
                            self.step_event.clear()
                            while not self.step_event.is_set():
                                time.sleep(0.1)
                            self.step_event.clear()
                        exec(ln, context)
                except Exception as e:
                    print(f"Loop error: {e}")
                finally:
                    if step:
                        self.after(0, lambda: self.step_btn.configure(state="disabled"))
                        self.step_event = None
                        self._step_script_active = False

        threading.Thread(target=worker, daemon=True).start()

    # ----------------------- Test Execution ------------------------
    def start_test(self):
        if self.running:
            return
        if not self.test_name_var.get().strip():
            messagebox.showerror("Error", "Please enter a test name before starting the test.")
            self.test_name_entry.focus_set()
            return
        iter_str = self.iterations_var.get().strip()
        if not iter_str:
            messagebox.showerror("Error", "Please enter the number of iterations before starting the test.")
            self.iterations_entry.focus_set()
            return
        try:
            iterations = int(iter_str)
            if iterations <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Iterations must be a positive integer.")
            self.iterations_entry.focus_set()
            return
        if not self.save_test(show_message=False):
            return
        os.environ["MRLF_CALIBRATION_FILE"] = os.path.join(
            self.tests_dir, "sensor_calibrations.json"
        )
        if self.test_script_path and os.path.exists(self.test_script_path):
            os.environ["MRLF_TEST_SCRIPT"] = self.test_script_path
        else:
            os.environ.pop("MRLF_TEST_SCRIPT", None)
        os.makedirs(self.log_dir, exist_ok=True)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        name = self.test_name_var.get() or "test"
        log_path = os.path.join(self.log_dir, f"{timestamp}_{name}.csv")
        self.log_file_path = log_path
        # Build device map for logging (sensors, valves and pressure regulators)
        log_devices = {}
        for alias, obj in self.device_objects.items():
            if (
                hasattr(obj, "_get_force_value")
                or hasattr(obj, "read_position")
                or hasattr(obj, "active_valves")
                or hasattr(obj, "current_pressure")
            ):
                log_devices[alias] = obj
                try:
                    setattr(obj, "_logger_alias", alias)
                except Exception:
                    pass
        self.csv_logger = CSVLogger(log_path, log_devices)
        self.csv_logger.start()
        if not self.monitor or not self.monitor.winfo_exists():
            self.monitor = TestMonitor(self)
        else:
            self.monitor.deiconify()
            self.monitor.lift()
        self.running = True
        self.paused = False
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.pause_btn.configure(state="normal")
        self.resume_btn.configure(state="disabled")
        if self.step_mode_var.get():
            self.step_btn.configure(state="normal")
            self.step_event = threading.Event()
        else:
            self.step_btn.configure(state="disabled")
            self.step_event = None
        self._set_edit_state("disabled")
        # Ensure any configured ITV pressures are written before executing
        # setup code or the first test iteration.
        self._rewrite_itv_pressures()
        context = {"__name__": "__main__"}
        try:
            if self.test_script_path and os.path.exists(self.test_script_path):
                spec = importlib.util.spec_from_file_location(
                    "user_devices", self.test_script_path
                )
                devices_mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(devices_mod)
            else:
                devices_mod = types.ModuleType("user_devices")
            for name, obj in devices_mod.__dict__.items():
                if not name.startswith("_"):
                    context[name] = obj
            # Add any custom aliases for this test
            for section in ("al1342", "al2205"):
                for port in self.instance_map.get(section, {}):
                    alias = self.instance_map[section][port]
                    base = self.base_map[section][port]
                    if alias != base and base in context:
                        context[alias] = context[base]
            # Expose helpers for delays, threading and event logging
            context["Hold"] = Hold
            context["start_thread"] = start_thread
            context["record_event"] = record_event
        except Exception as e:
            print(f"Failed to load device objects: {e}")
        setup_code = self.setup_code
        loop_code = self.script_text.get("1.0", "end-1c")
        queue_writer = _QueueWriter(self.monitor_queue)
        def worker():
            with redirect_stdout(_Tee(queue_writer)):
                try:
                    exec(setup_code, context)
                except Exception as e:
                    print(f"Setup error: {e}")
                    self.running = False
                    return
                for i in range(iterations):
                    print(f"Iteration: {i + 1}")
                    self._rewrite_itv_pressures()
                    if not self.running:
                        break
                    while self.paused and self.running:
                        time.sleep(0.1)
                    if not self.running:
                        break
                    lines = [ln for ln in loop_code.splitlines() if ln.strip()]
                    for ln in lines:
                        while self.paused and self.running:
                            time.sleep(0.1)
                        if not self.running:
                            break
                        if self.step_event:
                            self.step_event.clear()
                            while not self.step_event.is_set() and self.running:
                                time.sleep(0.1)
                            if not self.running:
                                break
                        try:
                            exec(ln, context)
                        except Exception as e:
                            print(f"Loop error: {e}")
                            self.running = False
                            break
            should_prompt = self.running
            self.running = False
            self.after(0, lambda p=should_prompt: self.stop_test(prompt=p))
        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()

    def stop_test(self, prompt=False):
        """Stop the running test and reset UI state."""
        # Even if the test thread has already finished, allow this method to
        # reset the buttons so the user can start a new test.
        self.running = False

        if self.worker:
            self.worker.join(timeout=2)
            self.worker = None

        if getattr(self, "csv_logger", None):
            self.csv_logger.stop()
            self.csv_logger = None

        if "MRLF_CALIBRATION_FILE" in os.environ:
            del os.environ["MRLF_CALIBRATION_FILE"]
        if "MRLF_TEST_SCRIPT" in os.environ:
            del os.environ["MRLF_TEST_SCRIPT"]

        # Reset pause state in case the test was stopped while paused
        self.paused = False

        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.pause_btn.configure(state="disabled")
        self.resume_btn.configure(state="disabled")
        self.step_btn.configure(state="disabled")
        self.step_event = None
        self._set_edit_state("normal")

        if prompt:
            self._prompt_save_log()

    def pause_test(self):
        if not self.running:
            return
        self.paused = True
        self.pause_btn.configure(state="disabled")
        self.resume_btn.configure(state="normal")

    def resume_test(self):
        if not self.running:
            return
        if self.connection_lost and self.status_var.get() == "Connected":
            self._rewrite_itv_pressures()
            self.connection_lost = False
        self.paused = False
        self.pause_btn.configure(state="normal")
        self.resume_btn.configure(state="disabled")

    def step_once(self):
        if self.step_event:
            self.step_event.set()

    def step_script(self):
        """Run the current script one line at a time."""
        if not getattr(self, "_step_script_active", False):
            self.run_script(step=True)
        self.step_once()

    def _rewrite_itv_pressures(self):
        for obj in getattr(self, "device_objects", {}).values():
            if hasattr(obj, "set_pressure"):
                if hasattr(obj, "get_setup_state"):
                    try:
                        val = obj.get_setup_state()
                    except Exception:
                        val = None
                else:
                    try:
                        val = obj.current_pressure
                    except Exception:
                        val = None
                if val is not None:
                    try:
                        obj.set_pressure(val)
                    except Exception as e:
                        print(f"Failed to rewrite pressure for {obj}: {e}")

    def _prompt_save_log(self):
        """Ask the user for a log file name and move the temporary log."""
        if not self.log_file_path:
            return
        default_name = f"{self.test_name_var.get() or 'Test Name'}_Trial 1"
        while True:
            name = simpledialog.askstring(
                "Test Complete",
                "Enter a name for the log file:",
                initialvalue=default_name,
            )
            if name is None:
                break
            safe = re.sub(r"\W+", "_", name.strip())
            if not safe:
                continue
            target = os.path.join(self.log_dir, f"{safe}.csv")
            if os.path.exists(target):
                if not messagebox.askyesno(
                    "Overwrite File",
                    f"{target} already exists. Overwrite?",
                ):
                    continue
            try:
                os.replace(self.log_file_path, target)
                messagebox.showinfo("Saved", f"Log saved to {target}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save log file: {e}")
            break

    def _on_close(self):
        """Handle window closing and stop background tasks."""
        self._stop_connection_monitor.set()
        if self._connection_after_id:
            try:
                self.after_cancel(self._connection_after_id)
            except Exception:
                pass
        self.stop_test()
        self.destroy()

    # ----------------------- Test File Handling -------------------
    def _verify_mapping(self, imported_cfg):
        """Warn if the imported test's device mapping differs from current config."""
        if not imported_cfg:
            return
        current = {s: self.cfg.get(s, {}) for s in ("al1342", "al2205")}
        imported = {s: imported_cfg.get(s, {}) for s in ("al1342", "al2205")}
        if current != imported:
            try:
                messagebox.showwarning(
                    "Configuration Mismatch",
                    (
                        "Imported test uses a different device mapping.\n"
                        "Reconfigure the test cell to match the test's configuration."
                    ),
                )
            except Exception:
                pass

    def save_test(self, show_message=True):
        self.update_loop_script()
        name = self.test_name_var.get().strip()
        if not name:
            if show_message:
                messagebox.showerror("Error", "Please enter a test name.")
            return False
        # Export alias script reflecting configured device names
        self.test_script_path = self._export_device_alias_script(name)
        os.makedirs(self.tests_dir, exist_ok=True)
        fname = re.sub(r"\W+", "_", name)
        path = os.path.join(self.tests_dir, f"{fname}.json")
        self.setup_values = self._collect_setup_values()
        data = {
            "name": name,
            "setup": self.setup_code,
            "loop": self.script_text.get("1.0", "end-1c"),
            "iterations": self.iterations_var.get().strip(),
            "config": self.cfg,
            "device_names": self.instance_map,
            "script_file": os.path.basename(self.test_script_path),
            "setup_values": self.setup_values,
            "builder": self._serialize_loop_builder(),
        }
        try:
            with open(path, "w") as fh:
                json.dump(data, fh, indent=2)
            self.test_file_path = path
            if show_message:
                messagebox.showinfo("Saved", f"Test saved to {path}")
            return True
        except Exception as e:
            if show_message:
                messagebox.showerror("Error", f"Failed to save test: {e}")
            return False

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
        self.tests_dir = os.path.dirname(path)
        self.log_dir = self.tests_dir

        self.test_name_var.set(data.get("name", ""))

        imported_cfg = data.get("config", {})
        self.cfg = imported_cfg
        self.ip_address = self.cfg.get("ip_address", "192.168.XXX.XXX")
        self.library = gather_library(self.cfg)
        self.base_map = build_instance_map(self.cfg)

        saved_names = data.get("device_names")
        if saved_names:
            self.instance_map = saved_names
        else:
            self.reset_device_names()
        self.alias_class_map = build_alias_class_map(self.cfg, self.instance_map)
        self.populate_command_library()

        self.setup_code = data.get("setup", "")
        self.script_text.delete("1.0", "end")
        loop_code = data.get("loop", "")
        self.script_text.insert("1.0", loop_code)
        for sec in getattr(self, "loop_sections", []):
            for r in sec.loop_rows:
                r.destroy()
            sec.destroy()
        self.loop_sections = []
        builder = data.get("builder")
        if builder:
            self._load_loop_builder(builder)
        else:
            current_section = None
            for line in loop_code.splitlines():
                line = line.rstrip()
                if not line:
                    continue
                if line.startswith("#"):
                    name = line.lstrip("#").strip()
                    current_section = self.add_section(add_row=False)
                    current_section.name_var.set(name)
                    continue
                if current_section is None:
                    current_section = self.add_section(add_row=False)
                self.add_loop_row(current_section)
                row = current_section.loop_rows[-1]
                cmd_part = line.split("(", 1)[0].strip()
                if "." in cmd_part:
                    alias, cmd_name = cmd_part.split(".", 1)
                else:
                    alias, cmd_name = "General", cmd_part
                if alias in ["General"] + self._get_all_devices():
                    row.device_var.set(alias)
                else:
                    row.device_var.set("General")
                self._update_row_commands(row)
                row.command_var.set(cmd_name)
                self._build_param_fields(row)
                args = line[line.find("(")+1 : line.rfind(")")]
                arg_vals = [a.strip() for a in args.split(',')] if args.strip() else []
                for i, (pname, var, default) in enumerate(row.param_vars):
                    if i < len(arg_vals):
                        val = arg_vals[i]
                        if '=' in val:
                            val = val.split('=',1)[1].strip()
                        var.set(val)
            self.update_loop_script()
        self.iterations_var.set(data.get("iterations", ""))

        self.setup_values = data.get("setup_values", {})
        self.test_script_path = os.path.join(
            self.tests_dir, data.get("script_file", "")
        )
        if self.test_script_path and os.path.exists(self.test_script_path):
            os.environ["MRLF_TEST_SCRIPT"] = self.test_script_path
        else:
            os.environ.pop("MRLF_TEST_SCRIPT", None)

        self.device_objects = load_device_objects(
            self.cfg, self.base_map, self.ip_address
        )
        self.build_setup_widgets()
        self.refresh_instance_table()

    def new_test(self):
        current_filled = (
            self.test_name_var.get().strip()
            or self.setup_code.strip()
            or self.script_text.get("1.0", "end-1c").strip()
        )
        if current_filled:
            if messagebox.askyesno("Save Test", "Save current test before creating a new test?"):
                self.save_test()
        # Launch the Test Launcher for a new test rather than
        # allowing creation directly within the wizard.
        cmd = [sys.executable, "-m", "gui.TestLauncher"]
        subprocess.Popen(cmd, cwd=REPO_ROOT)
        self._on_close()

    def reconfigure_cell(self):
        current_filled = (
            self.test_name_var.get().strip()
            or self.setup_code.strip()
            or self.script_text.get("1.0", "end-1c").strip()
        )
        if current_filled:
            if messagebox.askyesno(
                "Save Test",
                "Save current test before reconfiguring the test cell?",
            ):
                if not self.save_test():
                    return
        if self.test_file_path and os.path.exists(self.test_file_path):
            cmd = [
                sys.executable,
                "-m",
                "gui.TestLauncher",
                "--reconfigure",
                self.test_file_path,
            ]
        else:
            cmd = [sys.executable, "-m", "gui.TestLauncher"]
        subprocess.Popen(cmd, cwd=REPO_ROOT)
        self._on_close()


if __name__ == "__main__":
    import argparse

    try:
        _lock_handle = _acquire_lock()
    except RuntimeError:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Test Wizard",
            "Another Test Wizard is already running.",
        )
        root.destroy()
        sys.exit(1)

    atexit.register(_release_lock, _lock_handle)

    parser = argparse.ArgumentParser()
    parser.add_argument("--test-name")
    parser.add_argument("--test-dir")
    parser.add_argument("--load-file")
    args = parser.parse_args()
    app = TestWizard(
        test_name=args.test_name,
        test_dir=args.test_dir,
        load_path=args.load_file,
    )
    app.mainloop()
