import time
import threading
import os
import sys

# Allow importing project modules when executed directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from decorators import test_command, device_class

"""
    ==================================
    ValveBank Class - Public Interface
    ==================================

    Purpose:
    --------
    Control a bank of 16 valves (1.A–8.B) via Modbus through an IO master.

    Constructor:
    ------------
    ValveBank(io_master, port_number)

    Public Methods:
    ---------------
    - valve_on(valve, duration=None): Turn valve on, optional timed auto-off.
    - valve_off(*valves): Turn off one or more valves.
    - all_off(): Turn off all valves.
    """

@device_class
class ValveBank:

    @classmethod
    def test_instructions(cls):
        return [
            {
                "title": "valve_on(valve, duration)",
                "content": (
                    "Use: Turns on specified valves in SY3000 valve bank\n"
                    "Inputs:\n"
                    "    - valve: Valve to turn on (e.g., 1.A, 1.B ... 8.A)\n"
                    "    - duration=: Time (sec) valve stays active\n"
                    "            - \"duration=None\" - Turns valve on indefinitely\n"
                    "Example:\n"
                    "    - valve_on(\"1.A\", duration=3) - Turns valve 1.A on for 3 sec\n"
                    "    - valve_on(\"1.B\", duration=None) - Turns valve 1.B on indefinitely"
                ),
            },
            {
                "title": "valve_off(*valves)",
                "content": (
                    "Use: Turns off specified valves\n"
                    "Inputs:\n"
                    "    - *valves: Valves to shut off, separated by ',' (e.g., 1.A... 8.A)\n"
                    "Example:\n"
                    "    - valve_off(\"1.A\", \"1.B\") - Turns valves 1.A & 1.B off"
                ),
            },
            {
                "title": "all_off()",
                "content": "Use: Turns off all valves in SY3000 valve bank",
            },
        ]

    @classmethod
    def setup_instructions(cls):
        return []


    VALVE_BITMASKS = {
        "1.A": 0x0100, "1.B": 0x0200,
        "2.A": 0x0400, "2.B": 0x0800,
        "3.A": 0x1000, "3.B": 0x2000,
        "4.A": 0x4000, "4.B": 0x8000,
        "5.A": 0x0001, "5.B": 0x0002,
        "6.A": 0x0004, "6.B": 0x0008,
        "7.A": 0x0010, "7.B": 0x0020,
        "8.A": 0x0040, "8.B": 0x0080,
    }

    # Map each valve to its paired valve. Only one valve in a pair can be
    # active at a time.
    PAIRED_VALVES = {
        "1.A": "1.B", "1.B": "1.A",
        "2.A": "2.B", "2.B": "2.A",
        "3.A": "3.B", "3.B": "3.A",
        "4.A": "4.B", "4.B": "4.A",
        "5.A": "5.B", "5.B": "5.A",
        "6.A": "6.B", "6.B": "6.A",
        "7.A": "7.B", "7.B": "7.A",
        "8.A": "8.B", "8.B": "8.A",
    }

    def __init__(self, io_master, port_number):
        self.io_master = io_master
        self.port_number = port_number
        self.register = self.io_master.id_write_register(self.port_number)
        self.active_valves = set()
        self._timers = {}
        self._lock = threading.Lock()

    def valve_on(self, valve, duration=None):
        """
        Turn on a valve. If duration is specified, turn off automatically.
        """
        if valve not in self.VALVE_BITMASKS:
            raise ValueError(f"Invalid valve name: {valve}")

        paired = self.PAIRED_VALVES.get(valve)

        def _activate():
            print(f"Valve {valve} ON")
            with self._lock:
                if paired and paired in self.active_valves:
                    self.active_valves.remove(paired)
                    timer = self._timers.pop(paired, None)
                    if timer:
                        timer.cancel()
                    print(f"Valve {paired} OFF (auto)")
                self.active_valves.add(valve)
                self._write_state()

        def _auto_off():
            with self._lock:
                self.active_valves.discard(valve)
                self._write_state()
                self._timers.pop(valve, None)
            print(f"Valve {valve} OFF (auto)")

        if duration is not None:
            _activate()
            timer = threading.Timer(duration, _auto_off)
            timer.daemon = True
            self._timers[valve] = timer
            timer.start()
            print(f"Valve {valve} ON for {duration} sec")
        else:
            _activate()
            print(f"Valve {valve} ON indefinitely")

    def valve_off(self, *valves):
        """
        Turn off one or more valves.
        """
        with self._lock:
            for valve in valves:
                if valve in self.active_valves:
                    self.active_valves.remove(valve)
                    timer = self._timers.pop(valve, None)
                    if timer:
                        timer.cancel()
                    print(f"Valve {valve} OFF")
                else:
                    print(f"Valve {valve} was not active")
            self._write_state()

    def all_off(self):
        """
        Turn off all valves.
        """
        with self._lock:
            for timer in self._timers.values():
                timer.cancel()
            self._timers.clear()
            self.active_valves.clear()
            self._write_state()
        print("All valves OFF")

    # ---------- Internal-only below ----------

    def _write_state(self):
        """
        Compose the Modbus word and write it to the register.
        """
        state = 0
        for valve in self.active_valves:
            state |= self.VALVE_BITMASKS[valve]
        try:
            self.io_master.write_register(self.register, state)
            print(f"[ValveBank] Wrote 0x{state:04X} to register {self.register}")
        except ConnectionError as e:
            print(f"[ValveBank Error] {e}")
