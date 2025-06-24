import PySimpleGUI as sg
from devices.PositionSensor_SDAT_MHS_M160 import _load_position_sensors, _log


def Calibrate_PosSensor_PSG():
    """Launch PySimpleGUI calibration GUI for all mapped position sensors."""
    sensors = _load_position_sensors()
    if not sensors:
        sg.popup("No position sensors mapped to Test Cell 1.")
        return

    layout = []
    stroke_keys = []
    for idx, (sensor, name, port) in enumerate(sensors):
        stroke_key = ("stroke", idx)
        stroke_keys.append(stroke_key)
        layout.append([
            sg.Text(f"{name} ({port})", size=(20, 1)),
            sg.Button("Calibrate Min", key=("min", idx)),
            sg.Button("Calibrate Max", key=("max", idx)),
            sg.Input(str(sensor.stroke_mm), size=(6, 1), key=stroke_key),
        ])

    layout.append([sg.Button("Finish Calibration")])

    window = sg.Window("Position Sensor Calibration", layout)

    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, None):
            break
        if isinstance(event, tuple):
            action, idx = event
            sensor, name, port = sensors[idx]
            if action == "min":
                value = sensor.calibrate_min()
                _log(f"{name} {port} MIN: {value}")
            elif action == "max":
                value = sensor.calibrate_max()
                _log(f"{name} {port} MAX: {value}")
        elif event == "Finish Calibration":
            all_valid = True
            for idx, (sensor, name, port) in enumerate(sensors):
                try:
                    length = float(values.get(("stroke", idx), sensor.stroke_mm))
                except (TypeError, ValueError):
                    sg.popup_error(f"Invalid stroke for {name}")
                    all_valid = False
                    break
                sensor.set_stroke_length(length)
                _log(f"{name} {port} STROKE: {length}")
            if all_valid:
                break

    window.close()


if __name__ == "__main__":
    Calibrate_PosSensor_PSG()

