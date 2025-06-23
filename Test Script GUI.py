import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText

# === Paths ===
DEVICE_SCRIPT = os.path.expanduser("C:/Users/ratrobby/Desktop/MRLF Repository/Test_Cell_1_Devices.py")


def extract_device_info():
    devices = {"AL1342": {}, "AL2205": {}}
    if not os.path.exists(DEVICE_SCRIPT):
        return devices

    with open(DEVICE_SCRIPT, "r") as f:
        lines = f.readlines()
        for line in lines:
            line = line.strip()
            if line.startswith("# AL1342 Port"):
                parts = line.split(":")
                port = parts[0].split()[-1]
                name = parts[1].strip()
                devices["AL1342"][f"Port {port}"] = name
            elif line.startswith("# AL2205 X1."):
                parts = line.split(":")
                port = parts[0].split()[-1]
                name = parts[1].strip()
                devices["AL2205"][f"{port}"] = name
    return devices


class TestScriptGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Test Cell 1 - Test Script Runner")
        self.geometry("1000x700")

        self.devices = extract_device_info()

        self.create_widgets()
        self.insert_script_template()

    def create_widgets(self):
        # Main layout
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True)

        # Script Editor
        self.editor = ScrolledText(main_frame, wrap="none", font=("Consolas", 11))
        self.editor.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        # Device Panel
        device_frame = ttk.Frame(main_frame, width=250)
        device_frame.pack(side="right", fill="y", padx=10, pady=10)
        ttk.Label(device_frame, text="Connected Devices", font=("Arial", 12, "bold")).pack(pady=5)

        for group, ports in self.devices.items():
            group_label = ttk.Label(device_frame, text=f"{group}:", font=("Arial", 10, "bold"))
            group_label.pack(anchor="w", pady=(10, 0))
            for port, name in ports.items():
                entry = f"{port}: {name}"
                ttk.Label(device_frame, text=entry).pack(anchor="w")

        # Control Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=20, pady=10)

        ttk.Button(btn_frame, text="Start", command=self.start_test, style="Start.TButton").pack(side="left", padx=10)
        ttk.Button(btn_frame, text="Pause", command=self.pause_test, style="Pause.TButton").pack(side="left", padx=10)
        ttk.Button(btn_frame, text="Resume", command=self.resume_test, style="Resume.TButton").pack(side="left", padx=10)
        ttk.Button(btn_frame, text="Stop", command=self.stop_test, style="Stop.TButton").pack(side="left", padx=10)

        # Styles
        style = ttk.Style()
        style.configure("Start.TButton", font=("Arial", 12, "bold"), foreground="green")
        style.configure("Stop.TButton", font=("Arial", 12, "bold"), foreground="red")
        style.configure("Pause.TButton", font=("Arial", 12, "bold"), foreground="blue")
        style.configure("Resume.TButton", font=("Arial", 12, "bold"), foreground="dark orange")

    def insert_script_template(self):
        template = (
            "# === Test Script Template ===\n"
            "# Auto-generated imports\n"
            "# Setup connected devices\n\n"
            "# --- Setup ---\n"
            "# e.g., itv_1.set_pressure(50)\n\n"
            "# --- Test Loop ---\n"
            "# e.g., valve_on('1.A', 5)\n\n"
            "# --- Data Logging ---\n"
            "# e.g., log(load_cell.read())\n\n"
            "# --- Iterations ---\n"
            "# e.g., for i in range(10):\n"
            "#     run_test_cycle()\n"
        )
        self.editor.insert("1.0", template)

    def start_test(self):
        messagebox.showinfo("Start", "Test started.")

    def pause_test(self):
        messagebox.showinfo("Pause", "Test paused after current iteration.")

    def resume_test(self):
        messagebox.showinfo("Resume", "Test resumed.")

    def stop_test(self):
        messagebox.showinfo("Stop", "Test stopped.")


if __name__ == "__main__":
    app = TestScriptGUI()
    app.mainloop()
