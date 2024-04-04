import logging
import socket

from dicttoxml import dicttoxml

from . import event as appevent

logger = logging.getLogger(__name__)

#TODO make operator change and settings change an app event to completely decouple
class N1MM:
    """Send N1MM style packets"""

    radio_info = {
        "app": "NOT1MM",
        "StationName": "",
        "RadioNr": "1",
        "Freq": "",
        "TXFreq": "",
        "Mode": "",
        "OpCall": "",
        "IsRunning": "False",
        "FocusEntry": "0",
        "EntryWindowHwnd": "0",
        "Antenna": "1",
        "Rotors": "",
        "FocusRadioNr": "1",
        "IsStereo": "False",
        "IsSplit": "False",
        "ActiveRadioNr": "1",
        "IsTransmitting": "False",
        "FunctionKeyCaption": "",
        "RadioName": "Brad",
        "AuxAntSelected": "-1",
        "AuxAntSelectedName": "",
    }

    contact_info = {
        "app": "NOT1MM",
        "contestname": "",
        "contestnr": "1",
        "timestamp": "",
        "mycall": "",
        "operator": "",
        "band": "",
        "rxfreq": "",
        "txfreq": "",
        "mode": "",
        "call": "",
        "countryprefix": "K",
        "wpxprefix": "",
        "stationprefix": "",
        "continent": "NA",
        "snt": "59",
        "sntnr": "",
        "rcv": "59",
        "rcvnr": "",
        "gridsquare": "",
        "exchange1": "",
        "section": "",
        "comment": "",
        "qth": "",
        "name": "",
        "power": "",
        "misctext": "",
        "zone": "5",
        "prec": "",
        "ck": "0",
        "ismultiplier1": "0",
        "ismultiplier2": "0",
        "ismultiplier3": "0",
        "points": "1",
        "radionr": "1",
        "RoverLocation": "",
        "RadioInterfaced": "0",
        "NetworkedCompNr": "0",
        "IsOriginal": 1,
        "NetBiosName": "",
        "IsRunQSO": 0,
        "Run1Run2": "",
        "ContactType": "",
        "StationName": "",
        "ID": "",
        "IsClaimedQso": 1,
        "oldcall": "",
    }

    contactdelete = {
        "app": "NOT1MM",
        "timestamp": "",
        "call": "",
        "contestnr": "1",
        "StationName": "",
        "ID": "",
    }

    def __init__(
        self,
        radioport="127.0.0.1:12060",
        contactport="127.0.0.1:12060",
        lookupport="127.0.0.1:12060",
        scoreport="127.0.0.1:12060",
    ):
        """
        Initialize the N1MM interface.

        Optional arguments are:

        - radioport, Where radio status messages go.
        - contactport, Where Add, Update, Delete messages go.
        - lookupport, Where callsign queries go.
        - scoreport, Where to send scores to.
        """
        self.radio_port = radioport
        self.contact_port = contactport
        self.lookup_port = lookupport
        self.score_port = scoreport
        self.send_radio_packets = False
        self.send_contact_packets = False
        self.send_lookup_packets = False
        self.send_score_packets = False
        self.contact_info["NetBiosName"] = socket.gethostname()
        appevent.register(appevent.QsoDeleted, self.send_contact_delete)
        appevent.register(appevent.QsoUpdated, self.send_contactreplace)
        appevent.register(appevent.QsoAdded, self.send_contact_info)
        appevent.register(appevent.RadioState, self.send_radio)
        appevent.register(appevent.ExternalLookupResult, self.send_lookup)

    def set_station_name(self, name):
        """Set the station name"""
        self.radio_info["StationName"] = name
        self.contact_info["StationName"] = name
        self.contactdelete["StationName"] = name

    def set_operator(self, name, is_run: bool):
        """Set Operators Name"""
        self.contact_info["operator"] = name
        self.radio_info["IsRunning"] = "True" if is_run else "False"

    def send_radio(self, event: appevent.RadioState):

        if self.send_radio_packets:
            payload = dict(self.radio_info)
            payload["Freq"] = event.vfoa_hz
            payload["TXFreq"] = event.vfoa_hz
            payload["Mode"] = event.mode
            payload["OpCall"] = self.contact_info["operator"]
            self._send(self.radio_port, payload, "RadioInfo")

    def send_contact_info(self, event: appevent.QsoAdded):
        if self.send_contact_packets:
            payload = dict(self.contact_info)
            payload["timestamp"] = event.qso["TS"]
            payload["oldcall"] = payload["call"] = event.qso["Call"]
            payload["txfreq"] = payload["rxfreq"] = event.qso["Freq"]
            payload["mode"] = event.qso["Mode"]
            payload["contestname"] = event.qso["ContestName"].replace("-", "")
            payload["contestnr"] = event.qso["ContestNR"]
            payload["stationprefix"] = event.qso["StationPrefix"]
            payload["wpxprefix"] = event.qso["WPXPrefix"]
            payload["IsRunQSO"] = event.qso["IsRunQSO"]
            payload["operator"] = event.qso["Operator"]
            payload["mycall"] = event.qso["Operator"]
            payload["StationName"] = payload["NetBiosName"] = event.qso["NetBiosName"]
            payload["IsOriginal"] = event.qso["IsOriginal"]
            payload["ID"] = event.qso["ID"]
            payload["points"] = event.qso["Points"]
            payload["snt"] = event.qso["SNT"]
            payload["rcv"] = event.qso["RCV"]
            payload["sntnr"] = event.qso["SentNr"]
            payload["rcvnr"] = event.qso["NR"]
            payload["ismultiplier1"] = event.qso.get("IsMultiplier1", 0)
            payload["ismultiplier2"] = event.qso.get("IsMultiplier2", 0)
            payload["ismultiplier3"] = event.qso.get("IsMultiplier3", 0)
            payload["section"] = event.qso["Sect"]
            payload["prec"] = event.qso["Prec"]
            payload["ck"] = event.qso["CK"]
            payload["zn"] = event.qso["ZN"]
            payload["power"] = event.qso["Power"]
            payload["band"] = event.qso["Band"]
            self._send(self.contact_port, payload, "contactinfo")

    def send_contactreplace(self, event: appevent.QsoUpdated):
        """Send replace"""
        if self.send_contact_packets:
            payload = dict(self.contact_info)
            payload["timestamp"] = event.qso_after["TS"]
            payload["contestname"] = event.qso_after["ContestName"].replace("-", "")
            payload["contestnr"] = event.qso_after["ContestNR"]
            payload["operator"] = event.qso_after["Operator"]
            payload["mycall"] = event.qso_after["Operator"]
            payload["band"] = event.qso_after["Band"]
            payload["mode"] = event.qso_after["Mode"]
            payload["stationprefix"] = event.qso_after["StationPrefix"]
            payload["continent"] = event.qso_after["Continent"]
            payload["gridsquare"] = event.qso_after["GridSquare"]
            payload["ismultiplier1"] = event.qso_after["IsMultiplier1"]
            payload["ismultiplier2"] = event.qso_after["IsMultiplier2"]

            payload["call"] = event.qso_after["Call"]
            payload["oldcall"] = event.qso_before["Call"]

            payload["rxfreq"] = str(int(float(event.qso_after["Freq"]) * 100))
            payload["txfreq"] = str(int(float(event.qso_after["QSXFreq"]) * 100))

            payload["snt"] = event.qso_after["SNT"]
            payload["rcv"] = event.qso_after["RCV"]
            payload["sntnr"] = event.qso_after["SentNr"]
            payload["rcvnr"] = event.qso_after["NR"]
            payload["exchange1"] = event.qso_after.get("Exchange1", "")
            payload["ck"] = event.qso_after["CK"]
            payload["prec"] = event.qso_after["Prec"]
            payload["section"] = event.qso_after["Sect"]
            payload["wpxprefix"] = event.qso_after["WPXPrefix"]
            payload["power"] = event.qso_after["Power"]

            payload["zone"] = event.qso_after["ZN"]

            payload["countryprefix"] = event.qso_after["CountryPrefix"]
            payload["points"] = event.qso_after["Points"]
            payload["name"] = event.qso_after["Name"]
            payload["misctext"] = event.qso_after["Comment"]
            payload["ID"] = event.qso_after["ID"]
            self._send(self.contact_port, payload, "contactreplace")

    def send_contact_delete(self, event: appevent.QsoDeleted):
        if self.send_contact_packets:
            payload = dict(self.contactdelete)
            payload["timestamp"] = event.qso["TS"]
            payload["call"] = event.qso["Call"]
            payload["contestnr"] = event.qso["ContestNR"]
            payload["ID"] = event.qso['ID']

            self._send(self.contact_port, payload, "contactdelete")

    def send_lookup(self, event: appevent.ExternalLookupResult):
        if self.send_lookup_packets:
            payload = dict(self.contact_info)
            payload["call"] = event.result.call
            self._send(self.lookup_port, payload, "lookupinfo")

    def _send(self, port_list, payload, package_name):
        """Send XML data"""
        # bytes_to_send = dicttoxml(
        #     payload,
        #     custom_root=package_name,
        #     attr_type=False,
        #     return_bytes=False,
        #     encoding="UTF-8",
        # )
        bytes_to_send = dicttoxml(payload, custom_root=package_name, attr_type=False)
        # dom = parseString(bytes_to_send)
        # output = dom.toprettyxml(indent="\t", newl="\r\n").encode()
        logger.debug("********* %s", f"{package_name} {port_list}")
        for connection in port_list.split():
            try:
                ip_address, port = connection.split(":")
                port = int(port)
            except ValueError as returned_error:
                logger.debug(
                    "%s", f"Bad IP:Port combination {connection} {returned_error}"
                )
                continue
            try:
                radio_socket = None
                radio_socket = socket.socket(
                    family=socket.AF_INET, type=socket.SOCK_DGRAM
                )
                logger.debug(
                    "********* %s", f"{ip_address} {int(port)} {bytes_to_send}"
                )
                radio_socket.sendto(
                    bytes_to_send,
                    (ip_address, int(port)),
                )
            except PermissionError as exception:
                logger.critical("%s", f"{exception}")
            except socket.gaierror as exception:
                logger.critical("%s", f"{exception}")
