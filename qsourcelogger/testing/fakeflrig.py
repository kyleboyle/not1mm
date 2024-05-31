"""Main PC does not have radio attached. So we'll make a fake flrig server."""
import logging
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler


logging.basicConfig(level=logging.WARNING)

radio_state = {
    "freq": "14120000",
    "mode": "USB",
    "bw": "2700",
    "ptt": 0,
}


class RequestHandler(SimpleXMLRPCRequestHandler):
    """Doc String"""

    rpc_paths = ("/RPC2",)


def get_vfo():
    """return frequency in hz"""
    return str(int(radio_state["freq"]))


def set_vfo(freq):
    """set frequency in hz"""
    logging.warning("%s", f"Frequency set to: {freq} {type(freq)}")
    radio_state["freq"] = freq
    return 0


def set_frequency(freq):
    """seturn frequency in hz"""
    logging.warning("%s", f"Frequency set to: {freq} {type(freq)}")
    radio_state["freq"] = freq
    return 0

def set_ptt(flag):
    """seturn frequency in hz"""
    logging.warning(f"set ptt {flag}")
    radio_state["ptt"] = flag
    return 0

def get_ptt():
    return radio_state["ptt"]

def get_mode():
    """return mode"""
    return radio_state["mode"]

def set_mode(mode):
    """set frequency in hz"""
    logging.warning("%s", f"Mode set to: {mode}")
    radio_state["mode"] = mode
    return 0

def get_bw():
    """return bandwidth"""
    return [radio_state["bw"], ""]


def set_bw(bandwidth):
    """set bandwidth"""
    logging.warning("%s", f"bandwidth set to: {bandwidth}")
    radio_state["bw"] = bandwidth

def get_power():
    return 100

def get_version():
    """return flrig version"""
    return "1.4.8"

def get_info():
    return f"""R:FakeRig
T: R
FA: 0
M: USB
L: {radio_state['bw']}
U: n / a
N: 0
Vol: 0
Mic: 0
Rfg: 15"""

print("Stupid server to fake an flrig CAT control server. binding to 0.0.0.0 : 12345")

# Create server
with SimpleXMLRPCServer(
    ("0.0.0.0", 12345),
    requestHandler=RequestHandler,
    logRequests=False,
    allow_none=True,
) as server:
    server.register_function(get_vfo, name="rig.get_vfo")
    server.register_function(get_mode, name="rig.get_mode")
    server.register_function(set_vfo, name="rig.set_vfo")
    server.register_function(set_frequency, name="rig.set_frequency")
    server.register_function(set_mode, name="rig.set_mode")
    server.register_function(get_bw, name="rig.get_bw")
    server.register_function(set_bw, name="rig.set_bw")
    server.register_function(get_version, name="main.get_version")
    server.register_function(set_ptt, name="rig.set_ptt")
    server.register_function(get_ptt, name="rig.get_ptt")
    server.register_function(get_power, name="rig.get_power")
    server.register_function(get_info, name="rig.get_info")
    server.register_introspection_functions()
    server.serve_forever()