
import logging
from datetime import datetime, timedelta

from PyQt6 import QtCore

from not1mm.cat import RigState
from not1mm.cat.RigState import RigState

from not1mm.lib import event as appevent
from . import RigState

# http://www.w1hkj.com/flrig-help/xmlrpc_server.html

logger = logging.getLogger("cat")

class AbstractCat:

    rig_poll_timer: QtCore.QTimer
    previous_state: RigState = None
    radio_state_broadcast_time = datetime.now()

    def get_state(self) -> RigState:
        raise NotImplementedError()

    def set_vfo(self, freq: int) -> RigState:
        raise NotImplementedError()

    def set_mode(self, mode: str) -> bool:
        raise NotImplementedError()

    def set_power(self, watts: int) -> bool:
        raise NotImplementedError()

    def set_ptt(self, is_on: bool) -> bool:
        raise NotImplementedError()

    def close(self):
        self.rig_poll_timer.stop()

    def start_poll_loop(self) -> None:
        self.rig_poll_timer = QtCore.QTimer()
        self.rig_poll_timer.timeout.connect(self._poll_radio)
        self.rig_poll_timer.start(250)

    def _poll_radio(self):
        state = self.get_state()

        if datetime.now() > self.radio_state_broadcast_time or self.previous_state != state:
            logger.debug("VFO: %s MODE: %s BW: %s", state.vfoa_hz, state.mode, state.bandwidth_hz)
            appevent.emit(appevent.RadioState(state))
            self.radio_state_broadcast_time = datetime.now() + timedelta(seconds=10)
        self.previous_state = state

