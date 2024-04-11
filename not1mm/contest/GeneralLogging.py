from .AbstractContest import *


class GeneralLogging(AbstractContest):

    _fields = [
        ContestField(name='rst_sent', display_label='RST Snd', space_tabs=True, stretch_factor=1, requires_validation=False),
        ContestField(name='rst_rcvd', display_label='RST Rcv', space_tabs=True, stretch_factor=1, requires_validation=False),
        ContestField(name='name', display_label='Name', space_tabs=False, stretch_factor=2, requires_validation=False),
        ContestField(name='comment', display_label='Comment', space_tabs=False, stretch_factor=2, requires_validation=False),
    ]

    def __init__(self, contest: Contest):
        super().__init__(contest)

    @staticmethod
    def get_cabrillo_name() -> str:
        return 'GEN-LOG'

    def get_dupe_type(self) -> DupeType:
        return DupeType.NONE

    def get_preferred_column_order(self) -> list[str]:
        return ['band', 'rst_sent', 'rst_rcvd', 'name', 'comment', 'mode', 'submode']

    def get_qso_fields(self) -> list[ContestField]:
        return self._fields

    def get_multiplier_fields(self) -> Optional[list[str]]:
        return super().get_multiplier_fields()

    @staticmethod
    def get_suggested_contest_setup() -> dict[str: str]:
        return {
            "band_category": "ALL",
            "mode_category": "MIXED",
            "operator_category": "SINGLE-OP",
            "station_category": "FIXED",
            "transmitter_category": "UNLIMITED",
        }

    def default_field_value(self, field_name) -> Optional[str]:
        return super().default_field_value(field_name)

    def pre_process_qso_log(self, qso: QsoLog):
        super().pre_process_qso_log(qso)

    def adif_headers(self):
        pass

    def adif_qso(self, qso: QsoLog):
        pass

    def cabrillo_headers(self):
        pass

    def cabrillo_qso(self, qso: QsoLog):
        pass