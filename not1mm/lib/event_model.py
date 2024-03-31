class AppEvent():
    pass

class SpotDx(AppEvent):
    de: str = None
    dx: str = None
    freq_hz: int = None

    def __init__(self, de, dx, freq_hz):
        self.de = de
        self.dx = dx
        self.freq_hz = freq_hz

class MarkDx(SpotDx):
    pass

class FindDx(SpotDx):
    dx: str = None

    def __init__(self, dx):
        self.dx = dx

class BandmapSpotNext(AppEvent):
    pass

class BandmapSpotPrev(AppEvent):
    pass


# TODO clients should access the db if they want source of truth on qsos
class WorkedList(AppEvent):
    worked: list = None

    def __init__(self, worked):
        self.worked = worked


class GetWorkedList(AppEvent):
    pass


class CallChanged(AppEvent):
    call: str = None

    def __init__(self, call):
        self.call = call

# something has changed in the log, dependents should reload
class UpdateLog(AppEvent):
    pass

class QsoAdded(AppEvent):
    qso: dict

    def __init__(self, qso):
        self.qso = qso


class GetContestColumns(AppEvent):
    pass


class ContestColumns(AppEvent):
    columns: list

    def __init__(self, columns):
        self.columns = columns


class Tune(AppEvent):
    freq_hz: int
    dx: str

    def __init__(self, freq_hz, dx):
        self.freq_hz = freq_hz
        self.dx = dx

class GetActiveContest(AppEvent):
    pass

class ActiveContest(AppEvent):
    contest: dict
    operator: str

    def __init__(self, contest, operator):
        self.contest = contest
        self.operator = operator

class RadioState(AppEvent):
    vfoa_hz: int
    vfob_hz: int
    mode: str
    bandwith_hz: int

    def __init__(self, vfoa_hz, vfob_hz, mode, bandwith_hz):
        self.vfoa_hz = vfoa_hz
        self.vfob_hz = vfob_hz
        self.mode = mode
        self.bandwith_hz = bandwith_hz

# TODO in memory database should be shared between components
class CheckSpots(AppEvent):
    spots: list
    def __init__(self, spots):
        self.spots = spots

class LoadDb(AppEvent):
    pass