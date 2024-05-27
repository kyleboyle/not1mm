from . import VhfGeneralLogging
from .AbstractContest import *
from ..lib import event


class VhfGeneralSerialLogging(VhfGeneralLogging):

    _fields = [
        ContestField(name='rst_sent', display_label='RST Sent', space_tabs=True, stretch_factor=1, max_chars=3),
        ContestField(name='stx_string', display_label='Exch Snt', space_tabs=False, stretch_factor=4, max_chars=255),
        ContestField(name='rst_rcvd', display_label='RST Rcv', space_tabs=True, stretch_factor=1, max_chars=3),
    ]

    _optional_fields = [
        ContestField(name='srx', display_label='Serial Rcv', space_tabs=True, stretch_factor=3, max_chars=5),
        ContestField(name='gridsquare', display_label='Gridsquare', space_tabs=True, stretch_factor=3, max_chars=8),
    ]

    _previously_saved_serial: Optional[int] = None

    def __init__(self, contest: Contest):
        super().__init__(contest)
        event.register(event.QsoUpdated, self.clear_serial)
        event.register(event.QsoDeleted, self.clear_serial)

    def clear_serial(self):
        self._previously_saved_serial = None

    @staticmethod
    def get_cabrillo_name() -> str:
        return 'VHFSerial'

    def get_dupe_type(self) -> DupeType:
        return DupeType.EACH_BAND_MODE

    @staticmethod
    def get_preferred_column_order() -> list[str]:
        return ['band', 'rst_sent', 'rst_rcvd', 'stx', 'stx_string', 'srx', 'srx_string', 'gridsquare', 'distance', 'mode', 'submode']

    def get_qso_fields(self) -> list[ContestField]:
        return self._fields

    def get_optional_qso_fields(self) -> list[ContestField]:
        return self._optional_fields

    @staticmethod
    def get_suggested_contest_setup() -> dict[str: str]:
        return {
            "band_category": "VHF-3-BAND",
            "mode_category": "FM",
            "operator_category": "SINGLE-OP",
            "station_category": "FIXED",
            "transmitter_category": "UNLIMITED",
            "sent_exchange": "001",
        }

    def get_serial_to_send(self) -> Optional[str]:
        if self._previously_saved_serial:
            return str(self._previously_saved_serial + 1)
        else:
            # get serial from DB
            newest_qso = self.contest_qso_select().order_by(QsoLog.time_on.desc()).get_or_none()
            if newest_qso and newest_qso.stx:
                return newest_qso.stx + 1
        return self.get_starting_serial()

    def intermediate_qso_update(self, qso: QsoLog, fields: Optional[list[str]]):
        if not qso.call and not qso.stx:
            qso.stx = self.get_serial_to_send()
            qso.stx_string = self.generate_sent_exchange(qso.stx)

    def pre_process_qso_log(self, qso: QsoLog):
        if not qso.srx_string:
            qso.srx_string = str(qso.srx) + ' ' + qso.gridsquare
        super().pre_process_qso_log(qso)
        self._previously_saved_serial = int(qso.stx)

