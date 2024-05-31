import logging
import time
from queue import Queue, SimpleQueue
from sys import platform

from PyQt6.QtCore import QMutex, QMutexLocker

from qsourcelogger.cat import AbstractCat, RigState

if platform == 'win32':

    logger = logging.getLogger(__name__)
    import win32com.client

    # copped from https://github.com/4Z1KD/omnipyrig/blob/main/omnipyrig/omnipyrig.py
    class OmniRigClient:
        # properties
        is_debug = False
        _omnirig = None
        rig = None
        _rig1 = None
        _rig2 = None

        # on/off enumeration
        OFF = 0
        ON = 1

        # mode enumeration
        MODE_SSB_L = 1
        MODE_SSB_U = 2
        MODE_CW_U = 3
        MODE_FM = 4
        MODE_AM = 5
        MODE_RTTY_L = 6
        MODE_CW_L = 7
        MODE_DATA_L = 8
        MODE_RTTY_U = 9
        MODE_DATA_FM = 10
        MODE_FM_N = 11
        MODE_DATA_U = 12
        MODE_AM_N = 13
        MODE_PSK = 14
        MODE_DATA_FM_N = 15

        # mode values
        SSB_L = 0x04000000
        SSB_U = 0x02000000
        CW_U = 0x00800000
        FM = 0x40000000
        AM = 0x20000000
        CW_L = 0x01000000
        DATA_L = 0x10000000
        DATA_U = 0x08000000

        @classmethod
        def mode_str(cls, omni_mode: int):
            if omni_mode == cls.SSB_L:
                return 'LSB'
            if omni_mode == cls.SSB_U:
                return 'USB'
            if omni_mode == cls.CW_U or omni_mode == cls.CW_L:
                return 'CW'
            if omni_mode == cls.DATA_U or omni_mode == cls.DATA_L:
                return 'DATA'
            if omni_mode == cls.AM:
                return 'AM'
            if omni_mode == cls.AM:
                return 'FM'


        # rit/xit
        RIT_ON = 0x00020000
        RIT_OFF = 0x00040000
        XIT_ON = 0x00080000
        XIT_OFF = 0x00100000

        # split
        SPLIT_ON = 0x00008000
        SPLIT_OFF = 0x00010000

        TX_OFF = 0x00200000
        TX_ON = 0x00400000

        # vfo
        VFO_AA = 128
        VFO_AB = 256
        VFO_BB = 512
        VFO_BA = 1024

        def __init__(self):
            # create an instance of the service
            # self._omnirig = win32com.client.gencache.EnsureDispatch("Omnirig.OmnirigX")
            self._omnirig = win32com.client.Dispatch("Omnirig.OmnirigX")

            # set default Rig
            self.rig = self._rig1 = self._omnirig.Rig1
            self._rig2 = self._omnirig.Rig2

        ############################### setters #########################

        def setFrequency(self, vfo_selector, frequency):
            frequency = self.safe_int(frequency)
            if (frequency):
                if vfo_selector.upper() == 'A':
                    self.rig.FreqA = frequency
                elif vfo_selector.upper() == 'B':
                    self.rig.FreqB = frequency

        def setMode(self, mode):
            mode = self.safe_int(mode)
            if (mode):
                if mode == self.MODE_CW_L:
                    self.rig.Mode = self.CW_L
                elif mode == self.MODE_CW_U:
                    self.rig.Mode = self.CW_U
                elif mode == self.MODE_SSB_L:
                    self.rig.Mode = self.SSB_L
                elif mode == self.MODE_SSB_U:
                    self.rig.Mode = self.SSB_U
                elif mode == self.MODE_DATA_L:
                    self.rig.Mode = self.DATA_L
                elif mode == self.MODE_DATA_U:
                    self.rig.Mode = self.DATA_U
                elif mode == self.MODE_FM:
                    self.rig.Mode = self.FM
                elif mode == self.MODE_AM:
                    self.rig.Mode = self.AM

        def setRit(self, state):
            state = self.safe_int(state)
            if (state):
                if state == self.ON:
                    self.rig.Rit = self.RIT_ON
                if state == self.OFF:
                    self.rig.Rit = self.RIT_OFF

        def setXit(self, state):
            state = self.safe_int(state)
            if (state):
                if state == self.ON:
                    self.rig.Xit = self.XIT_ON
                if state == self.OFF:
                    self.rig.Xit = self.XIT_OFF

        def setRitOffset(self, offset):
            offset = self.safe_int(offset)
            if (offset):
                self.rig.ClearRit()
                self.rig.RitOffset = offset

        def setSplit(self, state):
            state = self.safe_int(state)
            if (state):
                if state == self.ON:
                    # self._rig.SetSplitMode()
                    self.rig.Split = self.SPLIT_ON
                if state == self.OFF:
                    # self._rig.SetSimplexMode()
                    self.rig.Split = self.SPLIT_OFF

        def setPitch(self, pitch):
            pitch = self.safe_int(pitch)
            if (pitch):
                pitch = int(pitch / 10)
                pitch = int(pitch * 10)
                self.rig.Pitch = pitch

        def setVfoA(self):
            self.rig.Vfo = self.VFO_AA

        def setVfoB(self):
            self.rig.Vfo = self.VFO_BB

        def setVfoAB(self):
            self.rig.Vfo = self.VFO_AB

        def setVfoBA(self):
            self.rig.Vfo = self.VFO_BA

        def setActiveRig(self, index):
            if index == 1:
                self.rig = self._rig1
            elif index == 2:
                self.rig = self._rig2

        ############################ helpers ##############################
        def parseCommand(self, command_string):
            cmd, val = self.split_string(command_string)
            if cmd and val:
                cmd = cmd.upper()
                if cmd == 'FA':
                    self.setFrequency('A', val)
                elif cmd == 'FB':
                    self.setFrequency('B', val)
                elif cmd == 'MD':
                    self.setMode(val)
                elif cmd == 'RT':
                    self.setRit(val)
                elif cmd == 'XT':
                    self.setXit(val)
                elif cmd == 'RU':
                    self.setRitOffset(val)
                elif cmd == 'KP':
                    self.setPitch(val)
                elif cmd == 'AA':
                    self.setVfoA()
                elif cmd == 'BB':
                    self.setVfoB()
                elif cmd == 'AB':
                    self.setVfoAB()
                elif cmd == 'BA':
                    self.setVfoBA()
                else:
                    return  # raise ValueError("Invalid operator")

        def split_string(self, s):
            s = s.strip()
            if len(s) >= 2:
                first_two_letters = s[:2]
                rest_of_string = s[2:]
                return first_two_letters, rest_of_string
            else:
                return s, ""

        def showParams(self):
            for x in dir(self.rig):
                self.showParam(x)

        def showParam(self, param):
            if param == 'Freq':
                logger.info(f'Freq: {self.rig.Freq}')
            elif param == 'FreqA':
                logger.info(f'FreqA: {self.rig.FreqA}')
            elif param == 'FreqB':
                logger.info(f'FreqB: {self.rig.FreqB}')
            elif param == 'FrequencyOfTone':
                logger.info(f'FrequencyOfTone: {self.rig.FrequencyOfTone(0)}')
            elif param == 'GetRxFrequency':
                logger.info(f'GetRxFrequency: {self.rig.GetRxFrequency()}')
            elif param == 'GetTxFrequency':
                logger.info(f'GetTxFrequency: {self.rig.GetTxFrequency()}')
            elif param == 'Mode':
                logger.info(f'Mode: {hex(self.rig.Mode)}')
            elif param == 'Pitch':
                logger.info(f'Pitch: {self.rig.Pitch}')
            elif param == 'PortBits':
                logger.info(f'PortBits.Cts: {self.rig.PortBits.Cts}')
                logger.info(f'PortBits.Dsr: {self.rig.PortBits.Dsr}')
                logger.info(f'PortBits.Dtr: {self.rig.PortBits.Dtr}')
                logger.info(f'PortBits.Rts: {self.rig.PortBits.Rts}')
            elif param == 'ReadableParams':
                logger.info(f'ReadableParams: {self.rig.ReadableParams}')
            elif param == 'RigType':
                logger.info(f'RigType: {self.rig.RigType}')
            elif param == 'Rit':
                logger.info(f'Rit: {self.rig.Rit}')
            elif param == 'RitOffset':
                logger.info(f'RitOffset: {self.rig.RitOffset}')
            elif param == 'Split':
                logger.info(f'Split: {self.rig.Split}')
            elif param == 'Status':
                logger.info(f'Status: {self.rig.Status}')
            elif param == 'StatusStr':
                logger.info(f'StatusStr: {self.rig.StatusStr}')
            elif param == 'Tx':
                logger.info(f'Tx: {self.rig.Tx}')
            elif param == 'Vfo':
                logger.info(f'Vfo: {self.rig.Vfo}')
            elif param == 'WriteableParams':
                logger.info(f'WriteableParams: {self.rig.WriteableParams}')
            elif param == 'Xit':
                logger.info(f'Xit: {self.rig.Xit}')

        def safe_int(self, input_data):
            if isinstance(input_data, str):
                try:
                    return int(input_data.replace(".", ""))  # Remove decimal point
                except ValueError:
                    return None  # Return None if the string cannot be converted
            elif isinstance(input_data, (int, float)):
                if isinstance(input_data, float):
                    input_data = str(input_data).replace(".", "")  # Remove decimal point
                return int(input_data)
            else:
                return None  # Return None for other types


    class CatOmnirig(AbstractCat):

        failure_count = 0
        client: OmniRigClient

        # since the com object can only be written to by the thread that created it, maintain a queue of commands
        # to execute when the get state function is run.
        command_queue = SimpleQueue()

        def __init__(self, rig_num):
            super().__init__()
            self.mutex = QMutex()
            self.online = False
            self.rig_num = int(rig_num)

        def get_id(self):
            return 'omnirig'

        def connect(self):
            try:
                self.client = OmniRigClient()
                self.client.setActiveRig(2 if self.rig_num == 2 else 1)
                time.sleep(0.2) # com object seems to need some time to "seed"
                self.client.showParams()
                self.online = True
            except:
                logger.exception("could not init omnirig")
                self.online = False

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
                state.mode = OmniRigClient.mode_str(self.client.rig.Mode)
                state.is_ptt = self.client.rig.Tx == self.client.TX_ON
                state.is_split = self.client.rig.Split == self.client.SPLIT_ON

                state.vforx_hz = int(self.client.rig.GetRxFrequency())
                state.vfotx_hz = int(self.client.rig.GetTxFrequency())

                #state.power = self.server.rig.get_power()
                #state.bandwidth = ??

                while not self.command_queue.empty():
                    # execute any functions which are queued
                    self.command_queue.get_nowait()()

                return state
            except Exception as exception:
                self.online = False
                logger.exception("omnirig get state error")
                return RigState(error='Rig unreachable ' + str(exception))

        def set_vfo(self, freq: int) -> bool:
            locker = QMutexLocker(self.mutex)
            try:
                if self.online:
                    self.client.setFrequency('A', float(freq))
                    return True
            except Exception as exception:
                self.online = False
                logger.exception(f"omni rig set_vfo {freq} failed")
            return False

        def set_mode(self, mode: str) -> bool:
            locker = QMutexLocker(self.mutex)
            try:
                if self.online:
                    if mode == 'CW':
                        mode = OmniRigClient.MODE_CW_L
                    elif mode == 'DATA':
                        mode = OmniRigClient.MODE_DATA_U
                    elif mode == 'SSB' or mode == 'USB':
                        mode = OmniRigClient.MODE_SSB_U
                    elif mode == 'LSB':
                        mode = OmniRigClient.MODE_SSB_L
                    elif mode == 'FM':
                        mode = OmniRigClient.MODE_FM
                    self.command_queue.append(lambda: self.client.setMode(mode))
                    return True
            except:
                self.online = False
                logger.exception(f"omni rig set_mode {mode} failed")
            return False

        def set_power(self, watts) -> bool:
            return False

        def set_ptt(self, is_on: bool) -> bool:
            locker = QMutexLocker(self.mutex)
            self.command_queue.append(lambda: self.client.setMode(self.client.TX_ON if is_on else self.client.TX_OFF))
            return True


else:
    class CatOmnirig(AbstractCat):
        pass


if __name__ == "__main__":
    omni = CatOmnirig(1)
    omni.get_state()
