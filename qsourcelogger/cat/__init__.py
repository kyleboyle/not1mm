
import logging
from datetime import datetime, timedelta

from PyQt6 import QtCore
from PyQt6.QtCore import QThread, QEventLoop

from qsourcelogger.lib import event as appevent
from .RigState import RigState

logger = logging.getLogger("cat")
_DEFAULT_POLL_INTERVAL_MS = 250

# TODO send cw/morse through cat if supported (rigctld)
class AbstractCat(QThread):

    poll_interval_ms = _DEFAULT_POLL_INTERVAL_MS
    rig_poll_timer: QtCore.QTimer
    _backoff_count = 0

    previous_state: RigState = None
    radio_state_broadcast_time = datetime.now()

    def __init__(self):
        super().__init__()
        self.rig_poll_timer = QtCore.QTimer()
        self.rig_poll_timer.moveToThread(self)
        self.moveToThread(self)

    def get_id(self):
        raise NotImplementedError()

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

    def run(self) -> None:
        self.rig_poll_timer.timeout.connect(self._poll_radio)
        self.rig_poll_timer.start(self.poll_interval_ms)

        loop = QEventLoop()
        loop.exec()

    def close(self):
        self.quit()
        self.wait(400)

    def start_poll_loop(self) -> None:
        self.start()

    def _poll_radio(self):
        state = self.get_state()

        if datetime.now() > self.radio_state_broadcast_time or self.previous_state != state:
            #logger.debug("VFO: %s MODE: %s BW: %s", state.vfotx_hz, state.mode, state.bandwidth_hz)
            appevent.emit(appevent.RadioState(state))
            self.radio_state_broadcast_time = datetime.now() + timedelta(seconds=10)
        self.previous_state = state

    def reset_backoff(self):
        self._backoff_count = 0
        self.poll_interval_ms = _DEFAULT_POLL_INTERVAL_MS
        self.rig_poll_timer.stop()
        self.rig_poll_timer.start(self.poll_interval_ms)

    def fail_backoff(self):
        self._backoff_count += 1
        self.poll_interval_ms = self.poll_interval_ms * 20 * self._backoff_count
        self.rig_poll_timer.stop()
        self.rig_poll_timer.start(self.poll_interval_ms)
