from dataclasses import dataclass

from . import lookup
from ..model import Contest, Station, QsoLog


class AppEvent():
    pass


@dataclass
class SpotDx(AppEvent):
    de: str = None
    dx: str = None
    freq_hz: int = None

    def __init__(self, de, dx, freq_hz):
        self.de = de
        self.dx = dx
        self.freq_hz = float(int(freq_hz))

@dataclass
class MarkDx(SpotDx):
    def __init__(self, de, dx, freq_hz):
        self.de = de
        self.dx = dx
        self.freq_hz = float(int(freq_hz))


@dataclass
class FindDx(AppEvent):
    dx: str = None

    def __init__(self, dx):
        self.dx = dx

@dataclass
class BandmapSpotNext(AppEvent):
    pass

@dataclass
class BandmapSpotPrev(AppEvent):
    pass

@dataclass
class CallChanged(AppEvent):
    call: str = None


# something has changed in the log, dependents should reload
@dataclass
class QsoUpdated(AppEvent):
    qso: QsoLog


@dataclass
class QsoAdded(AppEvent):
    qso: QsoLog

@dataclass
class QsoDeleted(AppEvent):
    qso: QsoLog


@dataclass
class QsoUpdated(AppEvent):
    qso_before: QsoLog
    qso_after: QsoLog


@dataclass
class Tune(AppEvent):
    freq_hz: int = None
    dx: str = None

    def __init__(self, freq_hz, dx):
        if freq_hz:
            self.freq_hz = int(freq_hz)
        self.dx = dx


@dataclass
class GetActiveContest(AppEvent):
    pass


@dataclass
class GetActiveContestResponse(AppEvent):
    contest: Contest
    operator: str


@dataclass
class RadioState(AppEvent):
    vfoa_hz: int
    vfob_hz: int
    mode: str
    bandwith_hz: int

    def __init__(self, vfoa_hz, vfob_hz, mode, bandwith_hz):
        self.vfoa_hz = int(vfoa_hz)
        self.vfob_hz = vfob_hz
        self.mode = mode
        self.bandwith_hz = bandwith_hz

# TODO in memory database should be shared between components
@dataclass
class CheckSpots(AppEvent):
    spots: list[object]

    def __init__(self, spots: list[object]):
        self.spots = spots

@dataclass
class ExternalLookupResult(AppEvent):
    result: lookup.ExternalCallLookupService.Result

@dataclass
class ContestActivated(AppEvent):
    contest: Contest

@dataclass
class StationActivated(AppEvent):
    station: Station

