"""
callsign lookup classes for:
QRZ
HamDB
HamQTH
"""
import dataclasses
import logging
from functools import partial, partialmethod
from typing import Optional
import not1mm.lib.event as appevent
import xmltodict
import requests
from PyQt6 import QtNetwork
from PyQt6.QtCore import QObject, QUrl, QUrlQuery
from PyQt6.QtNetwork import QNetworkRequest, QNetworkReply

logger = logging.getLogger("lookup")


class ExternalCallLookupService(QObject):

    @dataclasses.dataclass
    class Result:
        call: str
        grid: str
        name: str
        nickname: str
        source_result: dict

        def __init__(self, call):
            self.call = call
            pass

    init_flag = False
    network_access_manager = QtNetwork.QNetworkAccessManager()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def did_init(self) -> bool:
        return self.init_flag

    def lookup(self, call: str) -> Optional[Result]:
        pass



class HamDBlookup(ExternalCallLookupService):
    """
    Class manages HamDB lookups.
    """
    call = ''
    def __init__(self, parent=None) -> None:
        super().__init__(parent=parent)
        self.init_flag = True
        self.url = "https://api.hamdb.org/"
        self.reply = None

    def lookup(self, call: str) -> ExternalCallLookupService.Result:
        self.call = call
        if not self.reply:
            self.reply = self.network_access_manager.get(QNetworkRequest(QUrl(self.url + call + "/xml/wfd_logger")))
            self.reply.finished.connect(self.handle_lookup)

    def handle_lookup(self):
        """
        Lookup a call on QRZ

        <?xml version="1.0" encoding="utf-8"?>
        <hamdb version="1.0">
        <callsign>
        <call>K6GTE</call>
        <class>G</class>
        <expires>11/07/2027</expires>
        <grid>DM13at</grid>
        <lat>33.8254731</lat>
        <lon>-117.9875229</lon>
        <status>A</status>
        <fname>Michael</fname>
        <mi>C</mi>
        <name>Bridak</name>
        <suffix/>
        <addr1>2854 W Bridgeport Ave</addr1>
        <addr2>Anaheim</addr2>
        <state>CA</state>
        <zip>92804</zip>
        <country>United States</country>
        </callsign>
        <messages>
        <status>OK</status>
        </messages>
        </hamdb>
        """
        er = self.reply.error()
        self.reply.deleteLater()
        if er != QtNetwork.QNetworkReply.NetworkError.NoError:
            logger.error(self.reply.errorString())
            self.reply = None
        else:
            result = ExternalCallLookupService.Result(self.call)
            rootdict = xmltodict.parse(str(self.reply.readAll(), 'utf-8'))
            self.reply = None
            root = rootdict.get("hamdb")
            if root:
                messages = root.get("messages")
                callsign = root.get("callsign")
            if messages:
                error_text = messages.get("status")
                logger.debug("HamDB: %s", error_text)
            if callsign:
                result.source_result = callsign
                logger.debug(f"HamDB: found callsign field, response call = {callsign.get('call', None)}")
                if self.call != callsign.get("call", None):
                    logger.warning(f"response callsign {callsign.get('call', None)} doesn't match requested callsign {self.call}. aborting external lookup")
                    return
                if callsign.get("grid"):
                    result.grid = callsign.get("grid")
                if callsign.get("fname"):
                    result.name = callsign.get("fname")
                if callsign.get("name"):
                    if not result.name:
                        result.name = callsign.get("name")
                    else:
                        result.name = f"{result.name} {callsign.get('name')}"
                if callsign.get("nickname"):
                    result.nickname = callsign.get("nickname")

            appevent.emit(appevent.ExternalLookupResult(result))


class QRZlookup(ExternalCallLookupService):
    """
    Class manages QRZ lookups. Pass in a username and password at instantiation.
    """
    init_flag = False

    def __init__(self, username: str, password: str, parent=None) -> None:
        super().__init__(parent=parent)
        self.call_reply = None
        self.session = False
        self.expiration = False
        self.username = username
        self.password = password
        self.qrzurl = "https://xmldata.qrz.com/xml/134/"
        self.message = False
        self.lastresult = False
        self.getsession()
        if self.session:
            self.init_flag = True

    def getsession(self) -> None:
        """
        Get QRZ session key.
        Stores key in class variable 'session'
        Error messages returned by QRZ will be in class variable 'error'
        Other messages returned will be in class variable 'message'

        <?xml version="1.0" ?>
        <QRZDatabase version="1.34">
        <Session>
            <Key>2331uf894c4bd29f3923f3bacf02c532d7bd9</Key>
            <Count>123</Count>
            <SubExp>Wed Jan 1 12:34:03 2013</SubExp>
            <GMTime>Sun Aug 16 03:51:47 2012</GMTime>
        </Session>
        </QRZDatabase>

        Session section fields
        Field	Description
        Key	a valid user session key
        Count	Number of lookups performed by this user in the current 24 hour period
        SubExp	time and date that the users subscription will expire - or - "non-subscriber"
        GMTime	Time stamp for this message
        Message	An informational message for the user
        Error	XML system error message
        """
        self.session = False

        url = QUrl(self.qrzurl)
        query = QUrlQuery()
        query.addQueryItem("username", self.username)
        query.addQueryItem("password", self.password)
        url.setQuery(query.query())

        self.session_reply = self.network_access_manager.get(QNetworkRequest(url))
        self.session_reply.finished.connect(self.handle_session)
        logger.info("attempting to connect to qrz auth")

        #payload = {"username": self.username, "password": self.password}
        #query_result = requests.get(self.qrzurl, params=payload, timeout=10.0)

    def handle_session(self):
        er = self.session_reply.error()
        self.session_reply.deleteLater()
        if er != QtNetwork.QNetworkReply.NetworkError.NoError:
            logger.error(self.session_reply.errorString())
        else:
            baseroot = xmltodict.parse(str(self.session_reply.readAll(), 'utf-8'))
            root = baseroot.get("QRZDatabase")
            if root:
                session = root.get("Session")
                logger.info(f"get session result: {root}")
                if session.get("Key"):
                    self.session = session.get("Key")
                    self.init_flag = True
                if session.get("SubExp"):
                    self.expiration = session.get("SubExp")
                if session.get("Error"):
                    self.error = session.get("Error")
                if session.get("Message"):
                    self.message = session.get("Message")
                if not self.session:
                    logger.error(
                        "key:%s error:%s message:%s",
                        self.session,
                        self.error,
                        self.message)

    def lookup(self, call: str, is_retry=False) -> None:
        """
        Lookup a call on QRZ. async result sent in app event
        """
        if self.session and not self.call_reply:
            self.call = call
            url = QUrl(self.qrzurl)
            query = QUrlQuery()
            query.addQueryItem("s", self.session)
            query.addQueryItem("callsign", call)
            url.setQuery(query.query())
            logger.debug(f"query {url}")
            self.call_reply = self.network_access_manager.get(QNetworkRequest(url))
            self.call_reply.finished.connect(self.handle_lookup)

    def handle_lookup(self):
        er = self.call_reply.error()
        self.call_reply.deleteLater()
        if er != QtNetwork.QNetworkReply.NetworkError.NoError:
            logger.error(self.call_reply.errorString())
            self.call_reply = None
        else:
            try:
                baseroot = xmltodict.parse(str(self.call_reply.readAll(), 'utf-8'))
                self.call_reply = None
            except:
                logger.exception("Error parsing qrz call search response")
                return
            logger.debug(f"xml lookup {baseroot}\n")
            root = baseroot.get("QRZDatabase")
            session = root.get("Session")

            if session.get('Error', None):
                logger.info(f"Lookup error: {session.get('Error')}")

            if not session.get("Key"):
                # key expired get a new one
                logger.info("qrz session key expired or missing, getting new one.")
                self.getsession()

            result = ExternalCallLookupService.Result(self.call)
            result.source_result = root.get("Callsign")
            if not result.source_result:
                # probably callsign not found
                return
            if self.call != result.source_result.get("call", None):
                logger.warning(
                    f"response callsign {result.source_result.get('call', None)} doesn't match requested callsign {self.call}. aborting external lookup")
                return

            result.name = result.source_result.get('name', None)
            if 'fname' in result.source_result:
                if result.name:
                    result.name = result.source_result['fname'] + ' ' + result.name
                else:
                    result.name = result.source_result['fname']

            result.grid = result.source_result.get('grid', None)
            result.nickname = result.source_result.get('nickname', None)
            appevent.emit(appevent.ExternalLookupResult(result))


class HamQTH(ExternalCallLookupService):
    """HamQTH lookup"""

    def __init__(self, username: str, password: str) -> None:
        """initialize HamQTH lookup"""
        self.username = username
        self.password = password
        self.url = "https://www.hamqth.com/xml.php"
        self.session = False
        self.error = False
        self.getsession()
        if self.session:
            self.init_flag = True


    def getsession(self) -> None:
        """get a session key"""
        self.session = False

        url = QUrl(self.url)
        query = QUrlQuery()
        query.addQueryItem("u", self.username)
        query.addQueryItem("p", self.password)
        url.setQuery(query.query())

        self.session_reply = self.network_access_manager.get(QNetworkRequest(url))
        self.session_reply.finished.connect(self.handle_session)
        logger.info("attempting to connect to auth session")


    def handle_session(self):
        er = self.session_reply.error()
        self.session_reply.deleteLater()
        if er != QtNetwork.QNetworkReply.NetworkError.NoError:
            logger.error(self.session_reply.errorString())
        else:
            baseroot = xmltodict.parse(str(self.session_reply.readAll(), 'utf-8'))
            self.session_reply.deleteLater()
            self.session_reply = None
            root = baseroot.get("HamQTH")
            session = root.get("session")
            if session:
                if session.get("session_id"):
                    self.session = session.get("session_id")
                    self.init_flag = True
                if session.get("error"):
                    logger.error(session.get("error"))
            logger.info("session: %s", self.session)

    def lookup(self, call: str, is_retry=False) -> Optional[ExternalCallLookupService.Result]:
        """
        Lookup a call on HamQTH
        """
        if self.session and not self.call_reply:
            self.call = call
            url = QUrl(self.self.url)
            query = QUrlQuery()
            query.addQueryItem("id", self.session)
            query.addQueryItem("callsign", call)
            query.addQueryItem("prg", "wfdlogger")
            url.setQuery(query.query())
            logger.debug(f"query {url}")
            self.call_reply = self.network_access_manager.get(QNetworkRequest(url))
            self.call_reply.finished.connect(self.handle_lookup)

    def handle_lookup(self):
        er = self.call_reply.error()
        self.call_reply.deleteLater()
        if er != QtNetwork.QNetworkReply.NetworkError.NoError:
            logger.error(self.call_reply.errorString())
            self.call_reply = None
        else:
            try:
                baseroot = xmltodict.parse(str(self.call_reply.readAll(), 'utf-8'))
                self.call_reply = None
            except:
                logger.exception("Error parsing qrz call search response")
                return
            logger.debug(baseroot)
            root = baseroot.get("HamQTH")
            search = root.get("search")
            session = root.get("session")
            if not search:
                if session:
                    if session.get("error"):
                        if session.get("error") == "Session does not exist or expired":
                            self.getsession()
                        logger.error(f"lookup {self.call}: {session.get('error')}")
                return
            result = ExternalCallLookupService.Result(self.call)
            result.source_result = search
            if search.get("grid"):
                result.grid = search.get("grid")
            if search.get("nick"):
                result.nickname = search.get("nick")
            if search.get("adr_name"):
                result.name = search.get("adr_name")
            appevent.emit(appevent.ExternalLookupResult(result))
