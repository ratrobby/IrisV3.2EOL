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
ValveBank_SY3000 = ValveBank(master, port_number=2)
PressureRegulator_ITV_1050_1 = PressureRegulatorITV1050(master, port_number=3)
PressureRegulator_ITV_1050_2 = PressureRegulatorITV1050(master, port_number=4)
UI_Button = UIButton(AL2205_Hub, x1_index=0)
PositionSensor_SDAT_MHS_M160_1 = PositionSensorSDATMHS_M160(AL2205_Hub, x1_index=1)
PositionSensor_SDAT_MHS_M160_2 = PositionSensorSDATMHS_M160(AL2205_Hub, x1_index=2)
LoadCell_LCM300 = LoadCellLCM300(AL2205_Hub, x1_index=3)

# Example generated mappings
# AL1342 Port X01: AL2205_Hub (AL2205_Hub)
# AL1342 Port X02: ValveBank_SY3000 (ValveBank_SY3000)
# AL1342 Port X03: PressureRegulator_ITV_1050_1 (PressureRegulator_ITV_1050)
# AL1342 Port X04: PressureRegulator_ITV_1050_2 (PressureRegulator_ITV_1050)
# AL2205 X1.0: UI_Button (UI_Button)
# AL2205 X1.1: PositionSensor_SDAT_MHS_M160_1 (PositionSensor_SDAT_MHS_M160)
# AL2205 X1.2: PositionSensor_SDAT_MHS_M160_2 (PositionSensor_SDAT_MHS_M160)
# AL2205 X1.3: LoadCell_LCM300 (LoadCell_LCM300)
