import platform
import sys

from . import fsutils
from .__main__ import run

plat = f"{sys.platform}-{platform.machine()}"
#sys.path.append(str(fsutils.APP_DATA_PATH / 'hamlib' / plat))

pref_ref = {
    "sounddevice": "default",
    "run_state": False,
    "command_buttons": False,
    "cw_macros": True,
    "bands_modes": True,
    "bands": ["160", "80", "40", "20", "15", "10"],
    "send_n1mm_packets": False,
    "n1mm_station_name": "Shack",
    "n1mm_operator": "Jimmy",
    "n1mm_radioport": "127.0.0.1:12060",
    "n1mm_contactport": "127.0.0.1:12060",
    "n1mm_lookupport": "127.0.0.1:12060",
    "n1mm_scoreport": "127.0.0.1:12060",
    "cwip": "127.0.0.1",
    "cwport": 6789,
    "cwtype": 0,
    "useserver": False,
    "cluster_server": "dxc.nc7j.com",
    "cluster_port": 7373,
    "cluster_filter": "Set DX Filter Not Skimmer AND SpotterCont = NA",
    "cluster_mode": "OPEN",
    "lookup_populate_name": True,
    "lookup_name_prefer_qso_history_name": False,
    "bandmap_spot_age_minutes": 3,
    "lookup_source_qrz": False,
    "lookup_source_hamdb": False,
    "lookup_source_hamqth": False,
    "lookup_username": "",
    "lookup_password": "",
    "lookup_firstname": False,
    "lookup_others": True,
    "cat_enable_flrig": False,
    "cat_flrig_ip": "localhost",
    "cat_flrig_port": 12345,
    "cat_enable_omnirig": False,
    "cat_enable_rigctld": False,
    "cat_rigctld_ip": "localhost",
    "cat_rigctld_port": 4532,
    "cat_enable_manual": True,
    "cat_manual_mode": "SSB",
    "cat_manual_vfo": 14250000
}
