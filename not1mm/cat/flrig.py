import http
import xmlrpc.client

from .rigctld import AbstractCat, logger
from . import RigState


class CatFlrig(AbstractCat):

    def __init__(self, host, port):
        self.server = None
        self.host = host
        self.port = port
        self.online = False

    def connect(self):
        target = f"http://{self.host}:{self.port}"
        logger.debug("%s", target)
        self.server = xmlrpc.client.ServerProxy(target)
        try:
            _ = self.server.main.get_version()
            self.online = True
        except (
                ConnectionRefusedError,
                xmlrpc.client.Fault,
                http.client.BadStatusLine,
        ):
            self.online = False

    def get_state(self):

        if not self.online:
            self.connect()
            if not self.online:
                return RigState(error='Rig unreachable')
        try:
            state = RigState()
            state.vfoa_hz = int(self.server.rig.get_vfo())
            state.mode = self.server.rig.get_mode()
            state.is_ppt = self.server.rig.get_ptt() == '1'
            state.power = self.server.rig.get_power()
            state.bandwidth_hz = self.server.rig.get_bw()[0]
            return state
        except (
                ConnectionRefusedError,
                xmlrpc.client.Fault,
                http.client.BadStatusLine,
        ) as exception:
            self.online = False
            logger.exception("flrig get state error")
            return RigState(error='Rig unreachable ' + str(exception))

    def set_vfo(self, freq: int) -> bool:
        try:
            self.online = True
            return self.server.rig.set_frequency(float(freq))
        except (
                ConnectionRefusedError,
                xmlrpc.client.Fault,
                http.client.BadStatusLine,
        ) as exception:
            self.online = False
            logger.debug("setvfo_flrig: %s", f"{exception}")
        return False

    def set_mode(self, mode: str) -> bool:
        try:
            self.online = True
            return self.server.rig.set_mode(mode)
        except (
                ConnectionRefusedError,
                xmlrpc.client.Fault,
                http.client.BadStatusLine,
        ) as exception:
            self.online = False
            logger.debug("setmode_flrig: %s", f"{exception}")
        return False

    def set_power(self, watts) -> bool:
        try:
            self.online = True
            return self.server.rig.set_power(watts)
        except (
                ConnectionRefusedError,
                xmlrpc.client.Fault,
                http.client.BadStatusLine,
        ) as exception:
            self.online = False
            logger.debug("setpower_flrig: %s", f"{exception}")
            return False

    def set_ptt(self, is_on: bool) -> bool:
        try:
            self.online = True
            return self.server.rig.set_ptt(1 if is_on else 0)
        except (
                ConnectionRefusedError,
                xmlrpc.client.Fault,
                http.client.BadStatusLine,
        ) as exception:
            self.online = False
            logger.debug("%s", f"{exception}")
        return False
