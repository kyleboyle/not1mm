import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from . import Contest, Station, Enums
from ..lib.hamutils import cabrillo
from ..lib import hamutils
from ..model import QsoLog

logger = logging.getLogger(__name__)

def decimal_degress_to_degrees_minutes(decimal_degrees: float, is_lon=False):
    if decimal_degrees is None:
        return None
    direction = 'S' if decimal_degrees < 0 else 'N'
    if is_lon:
        direction = 'W' if decimal_degrees < 0 else 'E'
    dec = abs(decimal_degrees)
    return f"{direction}{int(dec):03} {(dec - int(dec)) * 60:02.3f}"

def degrees_minutes_to_decimal_degress(degrees_minutes: str):
    if degrees_minutes is None:
        return None
    parts = degrees_minutes.split(' ')
    return float(parts[1]) / 60 + int(parts[0][1:]) * (1 if parts[0][0] in ['N', 'E'] else -1)

def convert_qso_to_adif(qso: QsoLog) -> dict:
    adif = {}
    for field in QsoLog._meta.sorted_field_names:
        value = getattr(qso, field)
        if value is not None and value != '':
            if field in hamutils.adif.common.adif_rev_utf_field.keys():
                adif[hamutils.adif.common.adif_rev_utf_field[field]] = getattr(qso, field)
            elif field in hamutils.adif.common.adif_field:
                adif[field] = getattr(qso, field)

#        if field not in hamutils.adif.common.adif_rev_utf_field.keys() \
#            and field not in hamutils.adif.common.adif_field:
#            logger.debug(f"skipping qso field {field}")

    # handle specific model conversions
    del adif['time_on']
    adif['datetime_on'] = qso.time_on
    del adif['time_off']
    adif['datetime_off'] = qso.time_off
    adif['freq'] = adif['freq'] / 1_000_000
    if adif.get('freq_rx', None):
        adif['freq_rx'] = adif['freq_rx'] / 1_000_000
    adif['pfx'] = qso.wpx_prefix
    adif['cont'] = qso.continent
    adif['cnty'] = qso.county
    adif['my_cnty'] = qso.my_county
    adif['pfx'] = qso.prefix
    adif['class'] = qso.class_contest

    adif['lat'] = decimal_degress_to_degrees_minutes(adif['lat'])
    adif['my_lat'] = decimal_degress_to_degrees_minutes(adif['my_lat'])
    adif['lon'] = decimal_degress_to_degrees_minutes(adif['lon'], is_lon=True)
    adif['my_lon'] = decimal_degress_to_degrees_minutes(adif['my_lon'], is_lon=True)

    adif['app_qsource_id'] = str(qso.id)
    adif['app_qsource_fk_contest_id'] = int(qso.fk_contest.id)
    adif['app_qsource_fk_station_id'] = int(qso.fk_station.id)
    adif['app_qsource_points'] = qso.points
    adif['app_qsource_is_original'] = qso.is_original
    adif['app_qsource_hostname'] = qso.hostname
    adif['app_qsource_is_run'] = qso.is_run
    if qso.other:
        adif.update(dict(qso.other))
    return adif


def convert_adif_to_qso(adif: dict) -> QsoLog:
    qso = QsoLog()
    for key, value in adif.items():
        if key == 'datetime_on':
            qso.time_on = value
        elif key == 'datetime_off':
            qso.time_off = value
        elif key == 'freq':
            qso.freq = value * 1_000_000
        elif key == 'freq_rx':
            qso.freq_rx = value * 1_000_000
        elif key == 'pfx':
            qso.wpx_prefix = value
        elif key == 'cont':
            qso.continent = value
        elif key == 'cnty':
            qso.county = value
        elif key == 'my_cnty':
            qso.my_county = value
        elif key == 'pfx':
            qso.prefix = value
        elif key == 'class':
            qso.class_contest = value
        elif key == 'lat':
            qso.lat = degrees_minutes_to_decimal_degress(value)
        elif key == 'lon':
            qso.lon = degrees_minutes_to_decimal_degress(value)
        elif key == 'my_lat':
            qso.my_lat = degrees_minutes_to_decimal_degress(value)
        elif key == 'my_lon':
            qso.my_lon = degrees_minutes_to_decimal_degress(value)
        elif key == 'app_qsource_id':
            qso.id = uuid.UUID(value)
        elif key == 'app_qsource_fk_contest_id':
            matching_contest = Contest.select().where(Contest.id == value).get_or_none()
            if matching_contest:
                qso.fk_contest = matching_contest
        elif key == 'app_qsource_fk_station_id':
            matching_station = Station.select().where(Station.id == value).get_or_none()
            if matching_station:
                qso.fk_station = matching_station
        elif key == 'app_qsource_points':
            qso.points = value
        elif key == 'app_qsource_is_original':
            qso.is_original = value
        elif key == 'app_qsource_hostname':
            qso.hostname = value
        elif key == 'app_qsource_is_run':
            qso.is_run = value
        elif key in QsoLog._meta.sorted_field_names:
                setattr(qso, key, value)
        elif key in ['programid', 'programversion']:
            # ignore these fields
            pass
        else:
            if qso.other is None:
                qso.other = {}
            qso.other[key] = value

    return qso


@dataclass
class CabrilloRecord:
    freq: str = ""
    mode: str = ""
    timestamp: datetime = None
    operator_call: str = ""
    rst_sent: str = ""
    exchange_sent: str = ""
    call: str = ""
    rst_received: str = ""
    exchange_received: str = ""
    transmitter_id: int = 0


def convert_qso_to_cabrillo(qso: QsoLog) -> CabrilloRecord:
    record = CabrilloRecord()
    record.timestamp = qso.time_on
    record.freq = cabrillo.convert_to_freq_field(qso.freq)
    record.mode = Enums.adif_mode_to_cabrillo(qso.mode)
    record.operator_call = qso.operator or qso.station_callsign
    record.rst_sent = qso.rst_sent
    record.exchange_sent = qso.stx_string
    record.call = qso.call
    record.rst_received = qso.rst_rcvd
    record.exchange_received = qso.srx_string

    if qso.transmitter_id is not None and qso.transmitter_id == 0 or qso.transmitter_id == 1:
        record.transmitter_id = qso.transmitter_id

    return record
