from .AbstractContest import *


class GeneralLogging(AbstractContest):

    _fields = [
        ContestField(name='rst_sent', display_label='RST Snd', space_tabs=True, stretch_factor=1, max_chars=3),
        ContestField(name='rst_rcvd', display_label='RST Rcv', space_tabs=True, stretch_factor=1, max_chars=3),
    ]

    _optional_fields = [
        ContestField(name='name', display_label='Name', space_tabs=False, stretch_factor=4, max_chars=255),
        ContestField(name='comment', display_label='Comment', space_tabs=False, stretch_factor=4, max_chars=255),
    ]

    def __init__(self, contest: Contest):
        super().__init__(contest)

    @staticmethod
    def get_cabrillo_name() -> str:
        return 'DX'

    def get_dupe_type(self) -> DupeType:
        return DupeType.NONE

    @staticmethod
    def get_preferred_column_order() -> list[str]:
        return ['band', 'rst_sent', 'rst_rcvd', 'name', 'comment', 'mode', 'submode']

    def get_qso_fields(self) -> list[ContestField]:
        return self._fields

    def get_optional_qso_fields(self) -> list[ContestField]:
        return self._optional_fields

    def get_multiplier_fields(self) -> Optional[list[str]]:
        return super().get_multiplier_fields()

    @staticmethod
    def get_suggested_contest_setup() -> dict[str: str]:
        return {
            "band_category": "ALL",
            "mode_category": "SSB+CW+DIGITAL",
            "operator_category": "SINGLE-OP",
            "station_category": "FIXED",
            "transmitter_category": "UNLIMITED",
        }

    def intermediate_qso_update(self, qso: QsoLog, fields: Optional[list[str]]):
        if not qso.call and not qso.stx_string and self.contest.sent_exchange:
            qso.stx_string = self.contest.sent_exchange

    def calculate_total_points(self):
        return 0


