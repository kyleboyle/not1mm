import logging
import socket

from dicttoxml import dicttoxml

from . import event as appevent, ham_utility
from ..model import QsoLog

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

    def _qso_to_n1mm_dict(self, qso: QsoLog):
        payload = dict(self.contact_info)
        payload["timestamp"] = qso.time_on.strftime('%Y-%m-%d %H:%M:%S')
        payload["oldcall"] = payload["call"] = qso.call
        payload["txfreq"] = qso.freq / 10
        payload["rxfreq"] = qso.freq_rx / 10
        payload["mode"] = qso.mode
        payload["contestname"] = qso.fk_contest.fk_contest_meta.cabrillo_name.replace("-", "")
        payload["contestnr"] = qso.fk_contest.id
        payload["stationprefix"] = qso.station_callsign
        payload["wpxprefix"] = qso.wpx_prefix
        payload["IsRunQSO"] = qso.is_run
        payload["operator"] = qso.operator
        payload["mycall"] = qso.operator
        payload["StationName"] = payload["NetBiosName"] = qso.hostname
        payload["IsOriginal"] = qso.is_original
        payload["ID"] = qso.id
        payload["points"] = qso.points
        payload["snt"] = qso.rst_sent
        payload["rcv"] = qso.rst_rcvd
        payload["sntnr"] = qso.stx
        payload["rcvnr"] = qso.rtx
        #payload["ismultiplier1"] = False  # TODO
        #payload["ismultiplier2"] = False  # TODO
        #payload["ismultiplier3"] = False  # TODO
        payload["section"] = qso.arrl_sect
        payload["prec"] = qso.precedence
        payload["ck"] = qso.check
        payload["zn"] = qso.my_cq_zone
        #payload["power"] = ''  # TODO
        payload["band"] = ham_utility.get_n1mm_band(qso.freq)
        return payload

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
            payload = self._qso_to_n1mm_dict(event.qso)

            self._send(self.contact_port, payload, "contactinfo")

    def send_contactreplace(self, event: appevent.QsoUpdated):
        """Send replace"""
        if self.send_contact_packets:
            payload = self._qso_to_n1mm_dict(event.qso_after)
            payload["oldcall"] = event.qso_before.call
            self._send(self.contact_port, payload, "contactreplace")

    def send_contact_delete(self, event: appevent.QsoDeleted):
        if self.send_contact_packets:
            payload = self._qso_to_n1mm_dict(event.qso)
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
