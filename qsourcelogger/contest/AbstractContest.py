from dataclasses import dataclass
from enum import Enum
from typing import Optional

from qsourcelogger.model import QsoLog, Contest, Station
from qsourcelogger.model.adapters import CabrilloRecord


class DupeType(Enum):
    ONCE = 1  # a callsign only counts once
    EACH_BAND = 2  # a callsign can be logged in multiple bands
    EACH_BAND_MODE = 3  # a callsign can be logged for multiple modes in the same band
    NONE = 4  # duplicates don't matter


@dataclass(kw_only=True)
class ContestField:
    name: str
    display_label: str
    space_tabs: Optional[bool] = False
    callsign_space_to_here: Optional[bool] = False
    requires_validation: Optional[bool] = False
    stretch_factor: Optional[int] = 2
    max_chars: Optional[int] = 255


class ContestFieldNextLine(ContestField):
    def __init__(self):
        pass

class AbstractContest:
    """
    Defines interface contract and generic methods / default implementations for contest plugins
    """

    def __init__(self, contest: Contest):
        self.contest = contest
        self.points_per_contact = self.contest.fk_contest_meta.points_per_contact

    @staticmethod
    def get_cabrillo_name() -> str:
        """Must match one of the Contest Meta db entries"""
        raise NotImplementedError()

    def get_modes(self) -> list[str]:
        """
        CW DIGI FM RTTY SSB MIXED
        """
        return self.contest.fk_contest_meta.mode

    @staticmethod
    def get_suggested_contest_setup() -> dict[str: str]:
        """
        Pre-fill the contest settings page with these default options

        {
        "assisted_category": "value",
        "band_category": "value",
        "mode_category": "value",
        "operator_category": "value",
        "overlay_category": "value",
        "power_category": "value",
        "station_category": "value",
        "transmitter_category": "value",
        "operators": "value",
        "soapbox": "value",
        "sent_exchange": "value",
        }
        """
        pass

    def get_dupe_type(self) -> DupeType:
        raise NotImplementedError()

    @staticmethod
    def get_preferred_column_order() -> list[str]:
        """
        The db columns / qso fields that are important for this contest and given display priority in the
        QSO log table.
        Probably related to the qso fields.
        The first columns are always time_on and call sign, do not specify those here.
        """
        raise NotImplementedError()

    def get_qso_fields(self) -> list[ContestField]:
        """
        callsign is always the first field, is assumed, and has special behaviour. Do not specify it here.
        """
        raise NotImplementedError()

    def get_tab_order(self) -> list[str]:
        """
        gives the correct tab order of contest fields. callsign is always first. Using this list is how
        to define fields to skip by not including them.
        """
        return [x.name for x in self.get_qso_fields() if x.__class__ == ContestField]

    def get_multiplier_fields(self) -> Optional[list[str]]:
        """which combination of fields in the qso whose unique permutations constitute a multiplier."""
        pass

    def default_field_value(self, field_name) -> Optional[str]:
        """define a pre-filled value for the qso field."""
        pass

    def pre_process_qso_log(self, qso: QsoLog):
        """chance to mutate qso before it is persisted to the log database"""
        pass

    def intermediate_qso_update(self, qso: QsoLog, fields: Optional[list[str]]):
        """one or more fields have been modified"""
        pass

    def calculate_total_points(self):
        if not self.points_per_contact or self.points_per_contact == 0:
            return None

    def points_for_qso(self, qso: QsoLog) -> Optional[int]:
        if not self.points_per_contact or self.points_per_contact == 0:
            return None

    def cabrillo_headers(self, station: Station) -> list[tuple[2]]:
        """ by default, generate all the headers"""
        headers = [
            ('CONTEST', self.contest.fk_contest_meta.cabrillo_name),
            ('CALLSIGN', station.callsign),
            ('CATEGORY-OPERATOR', self.contest.operator_category),
            ('CATEGORY-ASSISTED', self.contest.assisted_category),
            ('CATEGORY-BAND', self.contest.band_category),
            ('CATEGORY-MODE', self.contest.mode_category),
            ('CATEGORY-TRANSMITTER', self.contest.transmitter_category),
            ('CATEGORY-OVERLAY', self.contest.overlay_category),
            ('GRID-LOCATOR', station.gridsquare),
            ('CATEGORY-POWER', self.contest.power_category),
            ('OPERATORS', ",".join([x.operator for x in QsoLog.select(QsoLog.operator.distinct())
                                   .where(QsoLog.fk_contest == self.contest)])),
        ]
        claimed_points = self.calculate_total_points()
        if claimed_points:
            headers.append(('CLAIMED-SCORE', claimed_points))
        if station.name:
            headers.append(('NAME', station.name))
        if station.club:
            headers.append(('CLUB', station.club))
        if station.arrl_sect:
            headers.append(("LOCATION", station.arrl_sect))
        if station.street1:
            headers.append(("ADDRESS", station.street1))
        if station.street2:
            headers.append(("ADDRESS", station.street2))
        if station.city:
            headers.append(("ADDRESS-CITY", station.city))
        if station.state:
            headers.append(("ADDRESS-STATE-PROVINCE", station.state))
        if station.postal_code:
            headers.append(("ADDRESS-POSTALCODE", station.postal_code))
        if station.country:
            headers.append(("ADDRESS-COUNTRY", station.country))
        if station.email:
            headers.append(("EMAIL", station.email))
        return headers

    def cabrillo_log(self, qso: QsoLog, cbr: CabrilloRecord) -> CabrilloRecord:
        return cbr

    def contest_qso_select(self):
        """helper for plugins to start a select statement which contains all qso's for the contest"""
        return QsoLog.select().where(QsoLog.fk_contest == self.contest)
