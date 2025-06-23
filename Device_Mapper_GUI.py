import os
import sys
import json
import tkinter as tk
from tkinter import ttk, messagebox
import importlib.util


# === Centralized Path & Utility Class ===
class DeviceUtils:
    DEVICE_FOLDER = r"C:\Users\ratrobby\Desktop\MRLF Repository\MRLF_Devices"
    CONFIG_FILE = r"C:\Users\ratrobby\Desktop\MRLF Repository\GUI Files\Device_Config.json"
    OUTPUT_FILES = {
        "Test Cell 1": r"C:\Users\ratrobby\Desktop\MRLF Repository\MRLF_Devices\Test_Cell_Device_Logs\Test_Cell_1_Devices.py",
    }
    DEFAULT_CONFIG = {
        "al1342": {str(i): "Empty" for i in range(1, 9)},
        "al2205": {f"X1.{i}": "Empty" for i in range(8)},
        "ip_address": "192.168.XXX.XXX"

    }
    DEFAULT_CONFIG["al1342"]["1"] = "AL2205_Hub"
    DEFAULT_CONFIG["al2205"]["X1.0"] = "read_UI_button"

    @staticmethod
    def get_class_name_from_file(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip().startswith("class "):
                    return line.strip().split()[1].split("(")[0].rstrip(":")
        return None

    @staticmethod
    def get_device_title(module_name):
        try:
            path = os.path.join(DeviceUtils.DEVICE_FOLDER, f"{module_name}.py")
            spec = importlib.util.spec_from_file_location(module_name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            for attr in dir(module):
                obj = getattr(module, attr)
                if isinstance(obj, type):
                    for method_name in ["title", "Title"]:
                        if hasattr(obj, method_name):
                            return getattr(obj(), method_name)()
            return module_name
        except Exception:
            return module_name

    @staticmethod
    def get_device_classes():
        devices = []
        for file in os.listdir(DeviceUtils.DEVICE_FOLDER):
            if file.endswith(".py") and file != "__init__.py":
                name = file[:-3]
                title = DeviceUtils.get_device_title(name)
                devices.append((title, name))
        return sorted(devices, key=lambda x: x[0].lower())

    @staticmethod
    def write_output_script(config, output_file, ip_address):
        """Generate a Python script defining device instances for this test cell."""
        al1342_config, al2205_config = config["al1342"], config["al2205"]

        lines = []

        # Add path patching for cross-folder imports
        lines.append("import sys")
        lines.append("import os")
        lines.append('sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))\n')

        # Start with core IO master import
        lines.append("from IO_master import IO_master")

        imports = {}
        instances = [f'master = IO_master("{ip_address}")']
        assignments = []

        all_devices = []
        for port, device_file in al1342_config.items():
            if device_file != "Empty":
                all_devices.append(("al1342", port, device_file))
        for port, device_file in al2205_config.items():
            if device_file != "Empty":
                all_devices.append(("al2205", port, device_file))

        device_counts = {}
        for _, _, device_file in all_devices:
            base = device_file.lower()
            device_counts[base] = device_counts.get(base, 0) + 1

        instance_numbers = {device: 1 for device in device_counts}

        for source, port, device_file in all_devices:
            module_path = os.path.join(DeviceUtils.DEVICE_FOLDER, f"{device_file}.py")
            class_name = DeviceUtils.get_class_name_from_file(module_path)
            if not class_name:
                continue

            imports[device_file] = class_name
            base_name = device_file.lower()
            count = device_counts[base_name]

            if count == 1:
                instance_name = base_name
            else:
                instance_name = f"{base_name}_{instance_numbers[base_name]}"
                instance_numbers[base_name] += 1

            if source == "al1342":
                instances.append(f"{instance_name} = {class_name}(master, port_number={port})")
                title = DeviceUtils.get_device_title(device_file)
                assignments.append(f"# AL1342 Port {port}: {instance_name} ({title})")
            else:
                x1_index = int(port.split(".")[1])
                instances.append(f"{instance_name} = {class_name}(al2205, x1_index={x1_index})")
                title = DeviceUtils.get_device_title(device_file)
                assignments.append(f"# AL2205 {port}: {instance_name} ({title})")

        for module, class_name in sorted(imports.items()):
            lines.append(f"from {module} import {class_name}")

        lines.append("")  # spacer
        lines.extend(instances)
        lines.append("")  # spacer
        lines.extend(assignments)

        with open(output_file, "w") as f:
            f.write("\n".join(lines))


class CalibrationPanel(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, borderwidth=2, relief='solid')
        ttk.Label(self, text="Calibrate Position Sensors", font=("Arial", 11, "bold", "underline")).pack(padx=10, pady=(10, 5))
        ttk.Button(self, text="Launch Calibration Window", command=launch_calibration_wizard, width=25).pack(padx=10, pady=10)


class IPAddressEntry(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, borderwidth=1, relief="solid")
        self.ip_var = tk.StringVar()
        ttk.Label(self, text="AL1342 IP Address:", width=20).pack(side="left", padx=(10, 5), pady=5)
        ttk.Entry(self, textvariable=self.ip_var, width=18).pack(side="left", padx=5, pady=5)

    def get(self):
        return self.ip_var.get()

    def set(self, value):
        self.ip_var.set(value)


class InstructionPanel(ttk.Frame):
    def __init__(self, parent, device_classes_func):
        super().__init__(parent, borderwidth=1, relief="solid")
        self.device_classes_func = device_classes_func

        ttk.Label(self, text="Device Instructions", font=("Arial", 10, "bold", "underline")).pack(pady=5)

        self.canvas = tk.Canvas(self, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner_frame = ttk.Frame(self.canvas)
        self.inner_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.populate_instruction_panel()

    def _get_device_instructions(self, module_name):
        try:
            module_path = os.path.join(DeviceUtils.DEVICE_FOLDER, f"{module_name}.py")
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            for attr in dir(module):
                obj = getattr(module, attr)
                if isinstance(obj, type) and hasattr(obj, "instructions"):
                    return obj.instructions()
        except Exception as e:
            print(f"Error loading instructions from {module_name}: {e}")
        return ""

    def populate_instruction_panel(self):
        for widget in self.inner_frame.winfo_children():
            widget.destroy()

        for title, module_name in self.device_classes_func():
            instructions = self._get_device_instructions(module_name)
            if instructions:
                setup_section = self._extract_section(instructions, "Test Setup Commands")
                test_section = self._extract_section(instructions, "Test Commands")

                container = ttk.Frame(self.inner_frame)
                container.pack(fill="x", padx=5, pady=5, anchor="w")

                # --- Section Header ---
                summary = ttk.Label(container, text=module_name, font=("Arial", 10, "bold"))
                summary.pack(anchor="w")

                if setup_section:
                    self._create_collapsible_text(container, "Test Setup Commands", setup_section)

                if test_section:
                    self._create_collapsible_text(container, "Test Commands", test_section)

    def _extract_section(self, instructions, section_title):
        import re
        pattern = rf"{section_title}\s*:(.*?)(\n[A-Z].*?:|\Z)"
        match = re.search(pattern, instructions, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _create_collapsible_text(self, parent, section_title, content):
        header = ttk.Label(parent, text=section_title, font=("Arial", 10, "bold italic"))
        header.pack(anchor="w", padx=10, pady=(4, 0))

        text_widget = tk.Text(parent, wrap="word", height=1, width=60, font=("Arial", 9), background="#f5f5f5")
        text_widget.insert("1.0", content)

        # Syntax highlight
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

        # Collapsible behavior
        text_widget.pack_forget()
        header.bind("<Button-1>", lambda e, t=text_widget: t.pack(fill="x", padx=10)
                    if not t.winfo_viewable() else t.pack_forget())


class DeviceSelectorFrame(ttk.Frame):
    def __init__(self, parent, label, count, device_classes):
        super().__init__(parent)

        self.vars = {}
        self.labels = {}

        ttk.Label(self, text=f"{label} Device Assignments", font=("Arial", 12, "bold")).pack(anchor="w", padx=10, pady=(5, 0))

        # Border frame
        self.border_frame = ttk.Frame(self, borderwidth=1, relief="solid")
        self.border_frame.pack(expand=True, fill="both", padx=5, pady=5)

        # Column headers
        header = ttk.Frame(self.border_frame)
        header.grid(row=0, column=0, sticky="ew", columnspan=3)
        ttk.Label(header, text="Port", font=("Arial", 10, "bold")).grid(row=0, column=0, padx=5, sticky="w")
        ttk.Label(header, text="Device", font=("Arial", 10, "bold")).grid(row=0, column=1, padx=5, sticky="w")
        ttk.Label(header, text="Status", font=("Arial", 10, "bold")).grid(row=0, column=2, padx=5, sticky="w")

        # Port rows
        for i in range(count):
            port = f"X{(i + 1):02d}" if label == "AL1342" else f"X1.{i}"

            ttk.Label(self.border_frame, text=f"{port}:").grid(row=i+1, column=0, padx=5, sticky="w")

            var = tk.StringVar()
            menu = ttk.Combobox(self.border_frame, textvariable=var, values=device_classes, state="readonly", width=30)
            menu.grid(row=i+1, column=1, sticky="w", padx=5)

            is_locked = (
                (label == "AL1342" and port == "X01") or
                (label == "AL2205" and port == "X1.0")
            )
            locked_value = "AL2205_Hub" if port == "X01" else "UI_Button" if port == "X1.0" else None

            if is_locked and locked_value:
                var.set(locked_value)
                def block_event(event): return "break"
                menu.bind("<Button-1>", block_event)
                menu.bind("<Key>", block_event)

            status = ttk.Label(self.border_frame, text="", width=12, anchor="w")
            status.grid(row=i+1, column=2, padx=5, sticky="w")

            self.vars[port] = var
            self.labels[port] = status




class DeviceTab(ttk.Frame):
    def __init__(self, master, cell_name):
        super().__init__(master)
        self.cell_name = cell_name

        device_tuples = DeviceUtils.get_device_classes()
        self.device_classes = ["Empty"] + [t[0] for t in device_tuples]
        self.device_map = {t[0]: t[1] for t in device_tuples}
        self.reverse_device_map = {v: k for k, v in self.device_map.items()}

        # Left-side container
        self.wrapper_frame = ttk.Frame(self)
        self.wrapper_frame.place(relx=0, rely=0, relwidth=0.52, relheight=0.5)

        # IP address entry
        self.ip_entry = IPAddressEntry(self.wrapper_frame)
        self.ip_entry.pack(fill="x", padx=10, pady=(10, 10))

        # Device assignments section
        self.port_frame = ttk.Frame(self.wrapper_frame)
        self.port_frame.pack(fill="both", expand=True, padx=10)

        # Create two side-by-side frames with equal weight
        self.port_frame.columnconfigure(0, weight=1, uniform="cols")
        self.port_frame.columnconfigure(1, weight=1, uniform="cols")

        # AL1342 Section
        al1342_container = ttk.Frame(self.port_frame, borderwidth=1, relief="solid")
        al1342_container.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=5)
        self.al1342_frame = DeviceSelectorFrame(al1342_container, "AL1342", 8, self.device_classes)
        self.al1342_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # AL2205 Section
        al2205_container = ttk.Frame(self.port_frame, borderwidth=1, relief="solid")
        al2205_container.grid(row=0, column=1, sticky="nsew", padx=(4, 0), pady=5)
        self.al2205_frame = DeviceSelectorFrame(al2205_container, "AL2205", 8, self.device_classes)
        self.al2205_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.al1342_vars = self.al1342_frame.vars
        self.al1342_labels = self.al1342_frame.labels
        self.al2205_vars = self.al2205_frame.vars
        self.al2205_labels = self.al2205_frame.labels

        # Assign Button
        ttk.Button(self.wrapper_frame, text=f"Assign {self.cell_name} Devices", command=self.generate).pack(pady=(5, 10))

        # --- Test Setup Section ---
        setup_frame = ttk.LabelFrame(self, text="Test Setup Commands", padding=(10, 5))
        setup_frame.place(relx=0.02, rely=0.55, relwidth=0.46, relheight=0.3)

        self.test_setup_box = tk.Text(setup_frame, wrap="word", font=("Consolas", 10), height=8)
        self.test_setup_box.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(setup_frame, command=self.test_setup_box.yview)
        scrollbar.pack(side="right", fill="y")
        self.test_setup_box.config(yscrollcommand=scrollbar.set)

        # --- Execute Button ---
        ttk.Button(self, text="Execute Test Setup", command=self.execute_test_setup).place(relx=0.02, rely=0.86)

        self.instructions_panel = InstructionPanel(self, device_classes_func=DeviceUtils.get_device_classes)
        self.instructions_panel.place(relx=0.7, rely=0.15, relwidth=0.3, relheight=0.5)

        self.load_configuration()

    def generate(self):
        config = {
            "al1342": {port: self.device_map.get(var.get(), "Empty") for port, var in self.al1342_vars.items()},
            "al2205": {port: self.device_map.get(var.get(), "Empty") for port, var in self.al2205_vars.items()},
            "ip_address": self.ip_entry.get()
        }
        DeviceUtils.write_output_script(config, DeviceUtils.OUTPUT_FILES[self.cell_name], config["ip_address"])
        self.save_configuration(config)
        messagebox.showinfo("Success", f"{self.cell_name} script created at:\n{DeviceUtils.OUTPUT_FILES[self.cell_name]}")
        self.update_status_labels()

    def save_configuration(self, config):
        all_configs = {}
        if os.path.exists(DeviceUtils.CONFIG_FILE):
            with open(DeviceUtils.CONFIG_FILE, "r") as f:
                all_configs = json.load(f)
        all_configs[self.cell_name] = config
        with open(DeviceUtils.CONFIG_FILE, "w") as f:
            json.dump(all_configs, f, indent=2)

    def load_configuration(self):
        if not os.path.exists(DeviceUtils.CONFIG_FILE):
            config = DeviceUtils.DEFAULT_CONFIG.copy()
        else:
            with open(DeviceUtils.CONFIG_FILE, "r") as f:
                all_configs = json.load(f)
                config = all_configs.get(self.cell_name, DeviceUtils.DEFAULT_CONFIG.copy())

        self.ip_entry.set(config.get("ip_address", "192.168.XXX.XXX"))
        for port, var in self.al1342_vars.items():
            var.set(self.reverse_device_map.get(config["al1342"].get(port, "Empty"), "Empty"))
        for port, var in self.al2205_vars.items():
            var.set(self.reverse_device_map.get(config["al2205"].get(port, "Empty"), "Empty"))

        config["al1342"]["X01"] = "AL2205_Hub"
        config["al2205"]["X1.0"] = "read_UI_button"
        self.al1342_vars["X01"].set(self.reverse_device_map["AL2205_Hub"])
        self.al2205_vars["X1.0"].set(self.reverse_device_map["UI_Button"])
        self.save_configuration(config)

        self.update_status_labels()

    def update_status_labels(self):
        try:
            with open(DeviceUtils.CONFIG_FILE, "r") as f:
                all_configs = json.load(f)
            last_config = all_configs.get(self.cell_name, {})
        except Exception:
            last_config = {}

        for port, var in self.al1342_vars.items():
            current = self.device_map.get(var.get(), "Empty")
            previous = last_config.get("al1342", {}).get(port, "Empty")
            locked = port == "X01"
            self._set_label_status(self.al1342_labels[port], current, previous, locked=locked)

        for port, var in self.al2205_vars.items():
            current = self.device_map.get(var.get(), "Empty")
            previous = last_config.get("al2205", {}).get(port, "Empty")
            locked = port == "X1.0"
            self._set_label_status(self.al2205_labels[port], current, previous, locked=locked)

    def _set_label_status(self, label, current, previous, locked=False):
        if locked:
            label.config(text="Locked", foreground="black", font=("Arial", 9, "bold"))
        elif current == "Empty":
            label.config(text="Empty", foreground="black", font=("Arial", 9))
        elif current == previous:
            label.config(text="Assigned", foreground="green", font=("Arial", 9))
        else:
            label.config(text="Unassigned", foreground="red", font=("Arial", 9))

    def generate(self):
        config = {
            "al1342": {port: self.device_map.get(var.get(), "Empty") for port, var in self.al1342_vars.items()},
            "al2205": {port: self.device_map.get(var.get(), "Empty") for port, var in self.al2205_vars.items()},
            "ip_address": self.ip_entry.get()
        }
        DeviceUtils.write_output_script(config, DeviceUtils.OUTPUT_FILES[self.cell_name], config["ip_address"])
        self.save_configuration(config)
        messagebox.showinfo("Success", f"{self.cell_name} script created at:\n{DeviceUtils.OUTPUT_FILES[self.cell_name]}")
        self.update_status_labels()

    def save_configuration(self, config):
        all_configs = {}
        if os.path.exists(DeviceUtils.CONFIG_FILE):
            with open(DeviceUtils.CONFIG_FILE, "r") as f:
                all_configs = json.load(f)
        all_configs[self.cell_name] = config
        with open(DeviceUtils.CONFIG_FILE, "w") as f:
            json.dump(all_configs, f, indent=2)

    def load_configuration(self):
        if not os.path.exists(DeviceUtils.CONFIG_FILE):
            config = DeviceUtils.DEFAULT_CONFIG.copy()
        else:
            with open(DeviceUtils.CONFIG_FILE, "r") as f:
                all_configs = json.load(f)
                config = all_configs.get(self.cell_name, DeviceUtils.DEFAULT_CONFIG.copy())

        self.ip_entry.set(config.get("ip_address", "192.168.XXX.XXX"))
        for port, var in self.al1342_vars.items():
            var.set(self.reverse_device_map.get(config["al1342"].get(port, "Empty"), "Empty"))
        for port, var in self.al2205_vars.items():
            var.set(self.reverse_device_map.get(config["al2205"].get(port, "Empty"), "Empty"))
        self.update_status_labels()

        # Ensure locked values are enforced
        config["al1342"]["X01"] = "AL2205_Hub"
        config["al2205"]["X1.0"] = "read_UI_button"
        self.al1342_vars["X01"].set(self.reverse_device_map["AL2205_Hub"])
        self.al2205_vars["X1.0"].set(self.reverse_device_map["UI_Button"])
        self.save_configuration(config)

    def update_status_labels(self):
        try:
            with open(DeviceUtils.CONFIG_FILE, "r") as f:
                all_configs = json.load(f)
            last_config = all_configs.get(self.cell_name, {})
        except Exception:
            last_config = {}

        for port, var in self.al1342_vars.items():
            current = self.device_map.get(var.get(), "Empty")
            previous = last_config.get("al1342", {}).get(port, "Empty")
            locked = port == "X01"
            self._set_label_status(self.al1342_labels[port], current, previous, locked=locked)

        for port, var in self.al2205_vars.items():
            current = self.device_map.get(var.get(), "Empty")
            previous = last_config.get("al2205", {}).get(port, "Empty")
            locked = port == "X1.0"
            self._set_label_status(self.al2205_labels[port], current, previous, locked=locked)

    def _set_label_status(self, label, current, previous, locked=False):
        if locked:
            label.config(text="Locked", foreground="black", font=("Arial", 9, "bold"))
        elif current == "Empty":
            label.config(text="Empty", foreground="black", font=("Arial", 9))
        elif current == previous:
            label.config(text="Assigned", foreground="green", font=("Arial", 9))
        else:
            label.config(text="Unassigned", foreground="red", font=("Arial", 9))

    def execute_test_setup(self):
        code = self.test_setup_box.get("1.0", "end-1c")
        if not code.strip():
            messagebox.showinfo("No Commands", "No setup commands to execute.")
            return
        try:
            local_context = globals().copy()
            exec(code, local_context)
            messagebox.showinfo("Success", "Test setup executed successfully.")
        except Exception as e:
            messagebox.showerror("Execution Error", f"Failed to execute setup:\n{e}")


class DeviceMapperApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MRLF Test Cell 1 Device Mapper")
        self.geometry("1800x950")
        style = ttk.Style()
        style.theme_use('default')
        style.configure("TNotebook.Tab", padding=[30, 10], font=('Arial', 12, 'bold'))

        # No notebook—just one panel
        self.device_tab = DeviceTab(self, "Test Cell 1")
        self.device_tab.pack(expand=True, fill="both")



# Launch GUI
if __name__ == "__main__":
    app = DeviceMapperApp()
    app.mainloop()
