from dataclasses import dataclass

from . import lookup

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


# TODO clients should access the db if they want source of truth on qsos
@dataclass
class WorkedList(AppEvent):
    worked: list = None

    def __init__(self, worked):
        self.worked = worked


@dataclass
class GetWorkedList(AppEvent):
    pass


@dataclass
class CallChanged(AppEvent):
    call: str = None

    def __init__(self, call):
        self.call = call

# something has changed in the log, dependents should reload
@dataclass
class UpdateLog(AppEvent):
    pass

@dataclass
class QsoAdded(AppEvent):
    qso: dict

    def __init__(self, qso):
        self.qso = qso

@dataclass
class QsoDeleted(AppEvent):
    qso: dict

    def __init__(self, qso):
        self.qso = qso

@dataclass
class QsoUpdated(AppEvent):
    qso_before: dict
    qso_after: dict

@dataclass
class GetContestColumns(AppEvent):
    pass


@dataclass
class ContestColumns(AppEvent):
    columns: list

    def __init__(self, columns):
        self.columns = columns


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
class ActiveContest(AppEvent):
    contest: dict
    operator: str

    def __init__(self, contest, operator):
        self.contest = contest
        self.operator = operator

@dataclass
class RadioState(AppEvent):
    vfoa_hz: int
    vfob_hz: int
    mode: str
    bandwith_hz: int

    def __init__(self, vfoa_hz, vfob_hz, mode, bandwith_hz):
        self.vfoa_hz = float(int(vfoa_hz))
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
class LoadDb(AppEvent):
    pass

@dataclass
class ExternalLookupResult(AppEvent):
    result: lookup.ExternalCallLookupService.Result
