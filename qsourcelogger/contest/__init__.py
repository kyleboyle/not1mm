from .GeneralLogging import GeneralLogging
from .GeneralSerialLogging import GeneralSerialLogging

contest_plugin_list = [
    GeneralLogging,
    GeneralSerialLogging
]

contests_by_cabrillo_id = dict([(x.get_cabrillo_name(), x) for x in contest_plugin_list])

# https://n1mmwp.hamdocs.com/manual-supported/contests-setup/setup-dx-contests/
# General Logging
# DXPedition
# DXSatellite
# General Serial