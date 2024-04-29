import logging
import socket
from typing import Optional

from PyQt6.QtCore import QMutex, QMutexLocker

from . import AbstractCat, RigState

logger = logging.getLogger(__name__)

class CatRigctld(AbstractCat):
    rigctrlsocket: Optional[socket.socket]

    def __init__(self, host: str, port: int) -> None:
        super().__init__()
        self.mutex = QMutex()
        self.rigctrlsocket = None
        self.host = host
        self.port = port
        self.online = False

    def get_id(self):
        return 'rigctld'

    def connect(self):
        self.close()
        try:
            self.rigctrlsocket = socket.socket()
            self.rigctrlsocket.settimeout(1)
            self.rigctrlsocket.connect((self.host, self.port))
            logger.debug("Connected to rigctrld")
            self.online = True
        except (ConnectionRefusedError, TimeoutError, OSError) as exception:
            self.rigctrlsocket = None
            self.online = False
            logger.exception("rigctld connection error")

    def close(self):
        if self.rigctrlsocket:
            self.rigctrlsocket.close()
            self.rigctrlsocket = None

    def get_info(self):
        locker = QMutexLocker(self.mutex)
        if not self.online:
            self.connect()
        if not self.online:
            return None
        try:
            self.rigctrlsocket.send(b"get_info\n")
            ret = self.rigctrlsocket.recv(2024).decode().strip()
            logger.debug(f"inventory from rigctld: {ret}")
        except:
            logger.exception("rigctld couldn't get inventory")
        finally:
            self.close()

    def get_state(self) -> RigState:
        locker = QMutexLocker(self.mutex)
        if not self.online:
            self.connect()
            if not self.online:
                return RigState(error='connection error')
        try:
            state = RigState(id=self.get_id())
            self.rigctrlsocket.send(b"f\n")
            vfo = self.rigctrlsocket.recv(1024).decode().strip()
            if "RPRT -" not in vfo:
                state.vfoa_hz = int(vfo)

            self.rigctrlsocket.send(b"m\n")
            mode = self.rigctrlsocket.recv(1024).decode().strip().split()
            state.mode = mode[0]
            state.bandwidth_hz = mode[1]

            self.rigctrlsocket.send(b"l RFPOWER\n")
            state.power = int(float(self.rigctrlsocket.recv(1024).decode().strip()) * 100)

            self.rigctrlsocket.send(b"t\n")
            state.is_ptt = self.rigctrlsocket.recv(1024).decode().strip == 1
            return state
        except IndexError as exception:
            logger.debug("%s", f"{exception}")
        except socket.error as exception:
            self.online = False
            logger.debug("%s", f"{exception}")
            self.rigctrlsocket = None
            RigState(error='Rig unreachable ' + str(exception))

    def set_vfo(self, freq: int) -> bool:
        """sets the radios vfo"""
        locker = QMutexLocker(self.mutex)
        if self.rigctrlsocket:
            try:
                self.rigctrlsocket.send(bytes(f"F {freq}\n", "utf-8"))
                _ = self.rigctrlsocket.recv(1024).decode().strip()
                return True
            except socket.error as exception:
                self.online = False
                logger.debug("setvfo_rigctld: %s", f"{exception}")
                self.rigctrlsocket = None
                return False
        return False

    def set_mode(self, mode: str) -> bool:
        """sets the radios mode"""
        locker = QMutexLocker(self.mutex)
        if self.rigctrlsocket:
            try:
                self.rigctrlsocket.send(bytes(f"M {mode} 0\n", "utf-8"))
                _ = self.rigctrlsocket.recv(1024).decode().strip()
                return True
            except socket.error as exception:
                self.online = False
                logger.debug("setmode_rigctld: %s", f"{exception}")
                self.rigctrlsocket = None
                return False
        return False

    def set_power(self, watts) -> bool:
        locker = QMutexLocker(self.mutex)

        if watts >= 1 and watts <= 100:
            rig_cmd = bytes(f"L RFPOWER {str(float(watts) / 100)}\n", "utf-8")
            try:
                self.rigctrlsocket.send(rig_cmd)
                _ = self.rigctrlsocket.recv(1024).decode().strip()
                return True
            except socket.error:
                self.online = False
                self.rigctrlsocket = None
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

        rig_cmd = bytes(f"T {1 if is_on else 0}\n", "utf-8")
        logger.debug("%s", f"{rig_cmd}")
        try:
            self.online = True
            self.rigctrlsocket.send(rig_cmd)
            _ = self.rigctrlsocket.recv(1024).decode().strip()
            return True
        except socket.error:
            self.online = False
            self.rigctrlsocket = None
            return False
