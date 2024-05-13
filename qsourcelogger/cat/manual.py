from abc import ABC

from qsourcelogger import fsutils
from qsourcelogger.cat import AbstractCat
from qsourcelogger.cat.RigState import RigState
from qsourcelogger.lib import event

class CatManual(AbstractCat):

    vfo: int = None
    mode: str = None
    power: int = None
    ptt = False
    settings: dict
    count = 0

    def __init__(self):
        super().__init__()
        self.settings = fsutils.read_settings()
        event.register(event.QsoAdded, self.event_qso_added)

    def connect(self):
        pass

    def event_qso_added(self, event: event.QsoAdded):
        if self.settings.get("cat_enable_manual", False):
            # track radio properties updated by the user
            self.mode = event.qso.mode
            self.vfo = event.qso.freq
            fsutils.write_settings({"cat_manual_vfo": self.vfo, "cat_manual_mode": self.mode})
            if event.qso.tx_pwr:
                self.power = event.qso.tx_pwr

    def get_state(self):
        if self.count % 10 == 0:
            self.settings = fsutils.read_settings()
            self.count += 1

        state = RigState()
        state.vforx_hz = self.vfo or self.settings.get("cat_manual_vfo")
        state.vfotx_hz = state.vforx_hz
        state.mode = self.mode or self.settings.get("cat_manual_mode")
        state.power = self.power
        state.id = "Manual"
        state.rig_name = "Manual"
        state.is_ptt = self.ptt
        return state

    def get_id(self):
        return 'Manual'

    def set_vfo(self, freq: int) -> bool:
        self.vfo = freq
        return True

    def set_mode(self, mode: str) -> bool:
        self.mode = mode
        return True

    def set_power(self, watts: int) -> bool:
        self.power = watts
        return True

    def set_ptt(self, is_on: bool) -> bool:
        self.ptt = is_on
        return True
