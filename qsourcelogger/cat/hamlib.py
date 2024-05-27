import logging

import serial
from PyQt6.QtCore import QMutex, QMutexLocker

from . import AbstractCat, RigState, libhamlib
from .libhamlib import Hamlib

logger = logging.getLogger(__name__)


class CatHamlib(AbstractCat):
    rig_model = None
    rig = None
    online = False
    failure_count = 0

    def __init__(self, rig_macro: str, rig_dev: str, rig_baud: str) -> None:
        super().__init__()
        self.mutex = QMutex()
        self.rig_macro = rig_macro
        self.rig_dev = rig_dev
        self.rig_baud = rig_baud
        self.rig_model = self.rig_macro

    def get_id(self):
        return 'hamlib'

    def connect(self):
        if not Hamlib:
            return
        try:
            rig_macro = getattr(Hamlib, self.rig_model)
            if Hamlib.rig_check_backend(rig_macro) != 0:
                raise Exception(f"{self.rig_model} backend check failed")

            # only check device existence for usb/serial rigs
            if Hamlib.rig_get_caps(rig_macro).serial_data_bits:
                if self.rig_dev not in [x.device for x in serial.tools.list_ports.comports()]:
                    raise Exception(f"{self.rig_model} connection error: {self.rig_dev} not available")

            self.rig = Hamlib.Rig(rig_macro)
            self.rig.set_conf("rig_pathname", self.rig_dev)
            self.rig.set_conf("retry", "0")
            if self.rig_baud:
                self.rig.set_conf("serial_speed", self.rig_baud)
            self.rig.open()

            if self.rig.error_status != 0:
                raise Exception(f"{self.rig_model} connection error: {Hamlib.rigerror(self.rig.error_status)}")

            logger.info(f"connected to {self.rig_model}, state: {self.rig.state}")

            self.online = True
        except Exception as exception:
            self.online = False
            logger.error(f"hamlib connection error {exception}")

    def close(self):
        if self.rig:
            self.rig.close()
            self.rig = None

    def get_state(self) -> RigState:
        locker = QMutexLocker(self.mutex)
        if not Hamlib:
            return RigState(id=self.get_id(), error='Hamlib not installed')

        if not self.online:
            self.connect()
            if not self.online:
                self.failure_count += 1
                if self.failure_count in [1, 2, 3]:
                    self.fail_backoff()
                return RigState(id=self.get_id(), error='Rig unreachable')
            self.reset_backoff()
            self.failure_count = 0
        try:
            state = RigState(id=self.get_id())

            vfo = self.rig.get_freq()
            if "RPRT -" not in str(vfo):
                state.vforx_hz = int(vfo)

            state.mode, state.bandwidth_hz = self.rig.get_mode()
            state.mode = libhamlib.mode_to_token(state.mode)
            # TODO figure out how to call self.rig.power2mW
            #state.power = self.rig.get_level_f(Hamlib.RIG_LEVEL_RFPOWER)

            state.is_ptt = int(self.rig.get_ptt()) > 0

            state.vfotx_hz = int(self.rig.get_split_freq())
            if state.vforx_hz != state.vfotx_hz:
                state.is_split = True

            return state
        except IndexError as exception:
            logger.error(exception)
        except Exception as e:
            self.online = False
            logger.error(f"get_status failed {e}")
            self.rig.close()
            self.rig = None
            RigState(error='Rig unreachable ' + str(e))

    def set_vfo(self, freq: int) -> bool:
        """sets the radios vfo"""
        locker = QMutexLocker(self.mutex)
        if self.online:
            try:
                self.rig.set_freq(self.rig.get_vfo(), freq)
                return True
            except Exception as e:
                self.online = False
                self.rig.close()
                self.rig = None
                logger.error(f"set_freq failed: {e}")
                return False
        return False

    def set_mode(self, mode: str) -> bool:
        """sets the radios mode"""
        locker = QMutexLocker(self.mutex)
        if self.online:
            try:
                if mode == 'CW':
                    mode = Hamlib.RIG_MODE_CW
                elif mode == 'DATA':
                    mode = Hamlib.RIG_MODE_PKTUSB
                elif mode == 'SSB' or mode == 'USB':
                    mode = Hamlib.RIG_MODE_USB
                elif mode == 'LSB':
                    mode = Hamlib.RIG_MODE_LSB
                elif mode == 'FM':
                    mode = Hamlib.RIG_MODE_FM
                self.rig.set_mode(mode, 0)
                return True
            except Exception as e:
                self.online = False
                self.rig.close()
                self.rig = None
                logger.error(f"set_mode failed: {e}")
                return False
        return False

    def set_power(self, watts) -> bool:
        locker = QMutexLocker(self.mutex)

        if watts >= 1 and watts <= 100:
            try:
                self.rig.set_level(str(float(watts) / 100))
                return True
            except Exception as e:
                self.online = False
                self.rig.close()
                self.rig = None
                logger.error(f"set_level failed: {e}")
                return False
        return False

    def set_ptt(self, is_on) -> bool:
        """Toggle PTT state on"""
        locker = QMutexLocker(self.mutex)

        # T, set_ptt 'PTT'
        # Set 'PTT'.
        # PTT is a value: ‘0’ (RX), ‘1’ (TX), ‘2’ (TX mic), or ‘3’ (TX data).

        # t, get_ptt
        # Get 'PTT' status.
        # Returns PTT as a value in set_ptt above.
        try:
            self.rig.set_ptt(self.rig.get_vfo(), 1 if is_on else 0)
            return True
        except Exception as e:
            self.online = False
            self.rig.close()
            self.rig = None
            logger.error(f"set_ptt failed: {e}")
            return False
