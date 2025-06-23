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

import time
import threading

# Public API decorator
def public_api(func):
    func._is_public_api = True
    return func

from decorators import test_setup, test_command

class ValveBank:
    @classmethod
    def instructions (cls):
        return """
    Command: ~valve_on(*valve, duration)~
    Use: Turns on specified valves in SY3000 valve bank   
    Inputs:
        - *valve: Valve to turn on (e.g., 1.A, 1.B ... 8.A)
        - duration=: Time (sec) valve stays active 
                - "duration=None" - Turns valve on indefinitely
    Example:
        - valve_on(1.A, duration = 3) - Turns valve 1.A on for 3 sec
        - valve_on(1.B, duration = None) - Turns valve 1.B on indefinitely

Command: ~valve_off(*valves)~
        Use: Turns off specified valves
        Inputs:
            - *valves: Valves to shut off, separated by "," (e.g., 1.A... 8.A)
        Example:
            - valve_off(1.A, 1.B) - Turns valves 1.A & 1.B off 
                    
Command: ~all_off()~
        Use: Turns off all valves in SY3000 valve bank
            """

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

    def __init__(self, io_master, port_number):
        self.io_master = io_master
        self.port_number = port_number
        self.register = self.io_master.id_write_register(self.port_number)
        self.active_valves = set()
        self._lock = threading.Lock()

    @test_command
    @public_api
    def valve_on(self, valve, duration=None):
        """
        Turn on a valve. If duration is specified, turn off automatically.
        """
        if valve not in self.VALVE_BITMASKS:
            raise ValueError(f"Invalid valve name: {valve}")

        def _turn_on_and_off():
            print(f"[Thread] Turning ON {valve} for {duration}s")
            with self._lock:
                self.active_valves.add(valve)
                self._write_state()
            time.sleep(duration)
            self.valve_off(valve)

        if duration is not None:
            threading.Thread(target=_turn_on_and_off, daemon=True).start()
        else:
            with self._lock:
                self.active_valves.add(valve)
                self._write_state()
            print(f"Valve {valve} ON indefinitely")

    @test_command
    @public_api
    def valve_off(self, *valves):
        """
        Turn off one or more valves.
        """
        with self._lock:
            for valve in valves:
                if valve in self.active_valves:
                    self.active_valves.remove(valve)
                    print(f"Valve {valve} OFF")
                else:
                    print(f"Valve {valve} was not active")
            self._write_state()

    @test_command
    @public_api
    def all_off(self):
        """
        Turn off all valves.
        """
        with self._lock:
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
