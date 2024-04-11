from .AbstractContest import *
from .GeneralLogging import GeneralLogging


class GeneralSerialLogging(GeneralLogging):

    _fields = [
        ContestField(name='rst_sent', display_label='Rst Sent', space_tabs=True, stretch_factor=1, requires_validation=False),
        ContestField(name='stx', display_label='Serial Snt', space_tabs=False, stretch_factor=2, requires_validation=False),
        ContestField(name='rst_rcvd', display_label='RST Rcv', space_tabs=True, stretch_factor=1, requires_validation=False),
        ContestField(name='srx', display_label='Serial Rcv', space_tabs=False, stretch_factor=2, requires_validation=False),
        ContestField(name='rst_rcvd', display_label='Name', space_tabs=True, stretch_factor=1, requires_validation=False),
        ContestFieldNextLine(),
        ContestField(name='name', display_label='Name', space_tabs=False, stretch_factor=2, requires_validation=False),
        ContestField(name='comment', display_label='comment', space_tabs=False, stretch_factor=2, requires_validation=False),
    ]

    #TODO blank out saved serial on qso edit

    _previously_saved_serial: int = None
    def __init__(self, contest: Contest):
        super().__init__(contest)

    @staticmethod
    def get_cabrillo_name() -> str:
        return 'GEN-LOG-SER'

    def get_dupe_type(self) -> DupeType:
        return DupeType.EACH_BAND_MODE

    def get_preferred_column_order(self) -> list[str]:
        return ['band', 'rst_sent', 'rst_rcvd', 'stx', 'srx', 'name', 'comment', 'mode', 'submode']

    def get_qso_fields(self) -> list[ContestField]:
        return self._fields

    @staticmethod
    def get_suggested_contest_setup() -> dict[str: str]:
        return {
            "band_category": "ALL",
            "mode_category": "MIXED",
            "operator_category": "SINGLE-OP",
            "station_category": "FIXED",
            "transmitter_category": "UNLIMITED",
            "sent_exchange": "001",
        }

    def default_field_value(self, field_name) -> Optional[str]:
        if field_name == 'stx':
            if self._previously_saved_serial:
                return str(self._previously_saved_serial + 1)
            else:
                # get serial from DB
                newest_qso = self.contest_qso_select().order_by(QsoLog.time_on.desc).get_or_none()
                if newest_qso:
                    return newest_qso.stx + 1
            return str(1)
        return super().default_field_value(field_name)

    def pre_process_qso_log(self, qso: QsoLog):
        super().pre_process_qso_log(qso)
        self._previously_saved_serial = qso.stx

    def adif_headers(self):
        pass

    def adif_qso(self, qso: QsoLog):
        pass

    def cabrillo_headers(self):
        pass

    def cabrillo_qso(self, qso: QsoLog):
        pass