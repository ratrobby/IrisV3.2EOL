import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from IO_master import IO_master
from devices.AL2205_Hub import AL2205Hub
from devices.LoadCell_LCM300 import LoadCellLCM300
from devices.PositionSensor_SDAT_MHS_M160 import PositionSensorSDATMHS_M160
from devices.PressureRegulator_ITV_1050 import PressureRegulatorITV1050
from devices.UI_Button import UIButton
from devices.ValveBank_SY3000 import ValveBank

master = IO_master("192.168.1.250")
AL2205_Hub = AL2205Hub(master, port_number=1)
ITV_1 = PressureRegulatorITV1050(master, port_number=2)
VB = ValveBank(master, port_number=3)
ITV_2 = PressureRegulatorITV1050(master, port_number=4)
ITV_3 = PressureRegulatorITV1050(master, port_number=6)
UI_Button = UIButton(AL2205_Hub, x1_index=0)
PS_1 = PositionSensorSDATMHS_M160(AL2205_Hub, x1_index=2)
LC_1 = LoadCellLCM300(AL2205_Hub, x1_index=3)
PS_2 = PositionSensorSDATMHS_M160(AL2205_Hub, x1_index=4)
LC_2 = LoadCellLCM300(AL2205_Hub, x1_index=5)
PS_3 = PositionSensorSDATMHS_M160(AL2205_Hub, x1_index=6)
LC_3 = LoadCellLCM300(AL2205_Hub, x1_index=7)

# Example generated mappings
# AL1342 Port X01: AL2205_Hub (AL2205_Hub)
# AL1342 Port X02: ITV_1 (PressureRegulator_ITV_1050)
# AL1342 Port X03: VB (ValveBank_SY3000)
# AL1342 Port X04: ITV_2 (PressureRegulator_ITV_1050)
# AL1342 Port X06: ITV_3 (PressureRegulator_ITV_1050)
# AL2205 X1.0: UI_Button (UI_Button)
# AL2205 X1.2: PS_1 (PositionSensor_SDAT_MHS_M160)
# AL2205 X1.3: LC_1 (LoadCell_LCM300)
# AL2205 X1.4: PS_2 (PositionSensor_SDAT_MHS_M160)
# AL2205 X1.5: LC_2 (LoadCell_LCM300)
# AL2205 X1.6: PS_3 (PositionSensor_SDAT_MHS_M160)
# AL2205 X1.7: LC_3 (LoadCell_LCM300)
