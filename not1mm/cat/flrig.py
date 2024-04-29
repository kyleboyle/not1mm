import http
import logging
import xmlrpc.client

from PyQt6.QtCore import QMutex, QMutexLocker

from . import AbstractCat, RigState

logger = logging.getLogger(__name__)

# http://www.w1hkj.com/flrig-help/xmlrpc_server.html

class CatFlrig(AbstractCat):

    failure_count = 0

    def __init__(self, host, port):
        super().__init__()
        self.mutex = QMutex()
        self.server = None
        self.host = host
        self.port = port
        self.online = False

    def get_id(self):
        return 'flrig'

    def connect(self):
        target = f"http://{self.host}:{self.port}"
        logger.debug("%s", target)

        transport = xmlrpc.client.Transport()
        con = transport.make_connection(self.host)
        con.timeout = 3

        self.server = xmlrpc.client.ServerProxy(target, transport=transport)

        try:
            _ = self.server.main.get_version()
            self.online = True
        except (
                TimeoutError,
                ConnectionRefusedError,
                xmlrpc.client.Fault,
                http.client.BadStatusLine,
        ):
            self.online = False

    def get_info(self):
        locker = QMutexLocker(self.mutex)
        if not self.online:
            self.connect()

        if self.online:
            try:
                info = self.server.rig.get_info()
                return info
            except (
                    ConnectionRefusedError,
                    xmlrpc.client.Fault,
                    http.client.BadStatusLine,
            ):
                logger.exception("Couldn't get flrig info")
                return None

    def get_state(self):
        locker = QMutexLocker(self.mutex)
        if not self.online:
            self.connect()
            if not self.online:
                self.failure_count += 1
                if self.failure_count == 10 or self.failure_count == 30:
                    self.fail_backoff()
                return RigState(error='Rig unreachable')
            self.reset_backoff()
            self.failure_count = 0
        try:
            state = RigState(id=self.get_id())
            state.vfoa_hz = int(self.server.rig.get_vfo())
            state.mode = self.server.rig.get_mode()
            state.is_ptt = self.server.rig.get_ptt() == '1'
            state.power = self.server.rig.get_power()
            try:
                state.bandwidth_hz = int(self.server.rig.get_bw()[0])
            except:
                ...
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
        locker = QMutexLocker(self.mutex)
        try:
            if self.online:
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
        locker = QMutexLocker(self.mutex)
        try:
            if self.online:
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
        locker = QMutexLocker(self.mutex)
        try:
            if self.online:
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
        locker = QMutexLocker(self.mutex)
        try:
            if self.online:
                return self.server.rig.set_ptt(1 if is_on else 0)
        except (
                ConnectionRefusedError,
                xmlrpc.client.Fault,
                http.client.BadStatusLine,
        ) as exception:
            self.online = False
            logger.debug("%s", f"{exception}")
        return False



#import xmlrpc
#with xmlrpc.client.ServerProxy("http://localhost:12346") as proxy:
#    result = proxy.rig.get_info()
#    print(str(result))
