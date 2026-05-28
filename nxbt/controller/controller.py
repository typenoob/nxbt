from enum import Enum
import logging


class ControllerTypes(Enum):
    """Controller type enumerations for initializing the controller server."""

    JOYCON_L = 1
    JOYCON_R = 2
    PRO_CONTROLLER = 3


class Controller:
    GAMEPAD_CLASS = "0x002508"
    SDP_UUID = "00001000-0000-1000-8000-00805f9b34fb"
    SDP_RECORD_PATH = "/nxbt/controller"
    ALIASES = {
        ControllerTypes.JOYCON_L: "Joy-Con (L)",
        ControllerTypes.JOYCON_R: "Joy-Con (R)",
        ControllerTypes.PRO_CONTROLLER: "Pro Controller",
    }

    def __init__(self, bluetooth, controller_type):
        self.bt = bluetooth
        self.logger = logging.getLogger("nxbt")

        if controller_type not in self.ALIASES:
            raise ValueError("Unknown controller type specified")
        self.alias = self.ALIASES[controller_type]
