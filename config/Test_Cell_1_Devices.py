import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from IO_master import IO_master
from devices.AL2205_Hub import AL2205
from devices.LoadCell_LCM300 import ReadLoadCell
from devices.PositionSensor_SDAT_MHS_M160 import PositionSensor
from devices.UI_Button import UI_Button

master = IO_master("192.168.1.250")
al2205_hub = AL2205(master, port_number="X01")
ui_button = UI_Button(al2205_hub, x1_index=0)
positionsensor_sdat_mhs_m160 = PositionSensor(al2205_hub, x1_index=2)
loadcell_lcm300 = ReadLoadCell(al2205_hub, x1_index=3)

# Example generated mappings
# AL1342 Port X01: al2205_hub (AL2205_Hub)
# AL2205 X1.0: ui_button (UI_Button)
# AL2205 X1.2: positionsensor_sdat_mhs_m160 (PositionSensor_SDAT_MHS_M160)
# AL2205 X1.3: loadcell_lcm300 (LoadCell_LCM300)
