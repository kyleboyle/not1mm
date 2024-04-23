from .AbstractContest import *
from .GeneralLogging import GeneralLogging
from ..lib import event


class GeneralSerialLogging(GeneralLogging):

    _fields = [
        ContestField(name='rst_sent', display_label='Rst Sent', space_tabs=True, stretch_factor=1, max_chars=3),
        ContestField(name='stx', display_label='Serial Snt', space_tabs=True, stretch_factor=2, max_chars=7),
        ContestField(name='rst_rcvd', display_label='RST Rcv', space_tabs=True, stretch_factor=1, max_chars=3),
        ContestField(name='srx', display_label='Serial Rcv', space_tabs=True, stretch_factor=2, callsign_space_to_here=True, max_chars=7),
        ContestFieldNextLine(),
        ContestField(name='name', display_label='Name', space_tabs=False, stretch_factor=4),
        ContestField(name='comment', display_label='comment', space_tabs=False, stretch_factor=4),
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
        return 'DXSerial'

    def get_dupe_type(self) -> DupeType:
        return DupeType.EACH_BAND_MODE

    @staticmethod
    def get_preferred_column_order() -> list[str]:
        return ['band', 'rst_sent', 'rst_rcvd', 'stx', 'srx', 'name', 'comment', 'mode', 'submode']

    def get_qso_fields(self) -> list[ContestField]:
        return self._fields

    @staticmethod
    def get_suggested_contest_setup() -> dict[str: str]:
        return {
            "band_category": "ALL",
            "mode_category": "SSB+CW+DIGITAL",
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
        return str(int(self.contest.sent_exchange or 1))

    def intermediate_qso_update(self, qso: QsoLog, fields: Optional[list[str]]):
        if not qso.call and not qso.stx:
            qso.stx = self.get_serial_to_send()

        super().intermediate_qso_update(qso, fields)

    def pre_process_qso_log(self, qso: QsoLog):
        qso.stx_string = str(qso.stx)
        qso.srx_string = str(qso.srx)
        super().pre_process_qso_log(qso)
        self._previously_saved_serial = int(qso.stx)


