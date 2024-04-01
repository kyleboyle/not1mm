#!/usr/bin/env python3
"""
K6GTE Contest logger
Email: michael.bridak@gmail.com
GPL V3
"""

# pylint: disable=unused-import, c-extension-no-member, no-member, invalid-name, too-many-lines
# pylint: disable=logging-fstring-interpolation, line-too-long, no-name-in-module

import logging
import os
import platform
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from json import loads

from PyQt6 import QtCore, QtGui, QtWidgets, uic, QtNetwork
from PyQt6.QtWidgets import QGraphicsView

import not1mm.fsutils as fsutils
from not1mm.lib import timeutils, ham_utility
import not1mm.lib.event as appevent

logger = logging.getLogger(__name__)

PIXELSPERSTEP = 10
UPDATE_INTERVAL = 2000

# TODO worked list can grow indefinitely. would probably be better to query database for dup or use common dupe code

class Band:
    """the band"""

    bands = {
        "160m": (1.8, 2),
        "80m": (3.5, 4),
        "60m": (5.102, 5.4065),
        "40m": (7.0, 7.3),
        "30m": (10.1, 10.15),
        "20m": (14.0, 14.35),
        "17m": (18.069, 18.168),
        "15m": (21.0, 21.45),
        "12m": (24.89, 25.0),
        "10m": (28.0, 29.7),
        "6m": (50.0, 54.0),
        "4m": (70.0, 71.0),
        "2m": (144.0, 148.0),
    }

    othername = {
        "160m": 1.8,
        "80m": 3.5,
        "60m": 5.1,
        "40m": 7.0,
        "30m": 10.0,
        "20m": 14.0,
        "17m": 18.0,
        "15m": 21.0,
        "12m": 24.0,
        "10m": 28.0,
        "6m": 50.0,
        "4m": 70.0,
        "2m": 144.0,
    }

    def __init__(self, band: str) -> None:
        self.start, self.end = self.bands.get(band, (0.0, 1.0))
        self.name = band
        self.altname = self.othername.get(band, 0.0)


class Database:
    """
    An in memory Database class to hold spots.
    """

    def __init__(self) -> None:
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.db.row_factory = self.row_factory
        cursor = self.db.cursor()
        sql_command = (
            "create table spots ("
            "callsign VARCHAR(15) NOT NULL, "
            "ts DATETIME NOT NULL, "
            "freq DOUBLE NOT NULL, "
            "mode VARCHAR(6), "
            "spotter VARCHAR(15) NOT NULL, "
            "comment VARCHAR(45));"
        )
        cursor.execute(sql_command)

        cursor.execute("CREATE INDEX spot_call_index ON spots (callsign);")
        cursor.execute("CREATE INDEX spot_freq_index ON spots (freq);")
        cursor.execute("CREATE INDEX spot_ts_index ON spots (ts);")

        self.db.commit()

    @staticmethod
    def row_factory(cursor, row):
        """
        cursor.description:
        (name, type_code, display_size,
        internal_size, precision, scale, null_ok)
        row: (value, value, ...)
        """
        return {
            col[0]: row[idx]
            for idx, col in enumerate(
                cursor.description,
            )
        }

    def get_like_calls(self, call: str) -> list:
        """
        Returns spots where the spotted callsigns contain the supplied string.

        Parameters
        ----------
        call : str
        The callsign to search for.

        Returns
        -------
        a dict like:

        {'K5TUX': [14.0, 21.0], 'N2CQR': [14.0], 'NE4RD': [14.0]}
        """
        try:
            cursor = self.db.cursor()
            cursor.execute(
                f"select distinct callsign from spots where callsign like ?;",
                (f"%{call.replace('?', '_')}%",)
            )
            result = cursor.fetchall()
            return result
        except sqlite3.OperationalError as exception:
            logger.debug("%s", exception)
            return {}

    def addspot(self, spot: dict, erase=True) -> None:
        """
        Add spot to database, replacing any previous spots with the same call.

        Parameters
        ----------
        spot: Dict
        A dict of the form: {'ts': datetime, 'callsign': str, 'freq': float,
        'band': str,'mode': str,'spotter': str, 'comment': str}

        erase: bool
        If True, delete any previous spots with the same callsign.
        If False, do not delete any previous spots with the same callsign.
        Default is True.

        Returns
        -------
        Nothing.
        """
        try:
            cursor = self.db.cursor()
            if erase:
                delete_call = "delete from spots where callsign = ?;"
                cursor.execute(delete_call, (spot.get("callsign"),))
                self.db.commit()

            cursor.execute(
                "INSERT INTO spots(callsign, ts, freq, mode, spotter, comment) VALUES(?, ?, ?, ?, ?, ?)",
                (
                    spot["callsign"],
                    spot["ts"],
                    spot["freq"],
                    spot.get("mode", None),
                    spot["spotter"],
                    spot.get("comment", None),
                ),
            )
            self.db.commit()
        except sqlite3.IntegrityError:
            ...

    def getspots(self) -> list:
        """
        Return a list of spots, sorted by the ascending frequency of the spot.

        Parameters
        ----------
        None

        Returns
        -------
        a list of dicts.
        """
        try:
            cursor = self.db.cursor()
            cursor.execute("select * from spots order by freq ASC;")
            return cursor.fetchall()
        except sqlite3.OperationalError:
            return ()

    def getspotsinband(self, start: float, end: float) -> list:
        """
        Returns spots in a list of dicts where the spotted frequency
        is in the range defined, in ascending order.

        Parameters
        ----------
        start : float
        The start frequency.
        end : float
        The end frequency.

        Returns
        -------
        A list of dicts.
        """
        return self.db.cursor().execute(
            "select * from spots where freq >= ? and freq <= ? order by freq ASC;",
            (start, end),
        ).fetchall()

    def get_next_spot(self, current: float, limit: float) -> dict:
        """
        Return a list of dict where freq range is defined by current and limit.
        The list is sorted by the ascending frequency of the spot.

        Parameters
        ----------
        current : float
        The current frequency.
        limit : float
        The limit frequency.

        Returns
        -------
        A dict of the spot.
        """
        return self.db.cursor().execute(
            "select * from spots where freq > ? and freq <= ? order by freq ASC;",
            (current, limit),
        ).fetchone()

    def get_matching_spot(self, dx: str, start: float, end: float) -> dict:
        """
        Return the first spot matching supplied dx partial callsign.

        Parameters
        ----------
        dx : str
        The dx partial callsign.
        start : float
        The start frequency.
        end : float
        The end frequency.

        Returns
        -------
        A dict of the spot.
        """

        return self.db.cursor().execute(
            "select * from spots where freq >= ? and freq <= ? and callsign like ?;",
            (start, end, f"%{dx}%"),
        ).fetchone()

    def get_prev_spot(self, current: float, limit: float) -> dict:
        """
        Return a list of dict where freq range is defined in descending order.

        Parameters
        ----------
        current : float
        The current frequency.
        limit : float
        The limit frequency.

        Returns
        -------
        A list of dicts.
        """
        return self.db.cursor().execute(
            "select * from spots where freq < ? and freq >= ? order by freq DESC;",
            (current, limit),
        ).fetchone()

    def delete_spots(self, minutes: int) -> int:
        """
        Delete spots older than the specified number of minutes.

        Parameters
        ----------
        minutes : int
        The number of minutes to delete.

        Returns
        -------
        None
        """
        return self.db.cursor().execute(
            "delete from spots where ts < datetime('now', ?);",
            (f"-{minutes} minutes",),
        ).rowcount


class BandMapWindow(QtWidgets.QDockWidget):
    """The BandMapWindow class."""

    zoom = 5
    currentBand = Band("20m")
    txMark = []
    rxMark = []
    rx_freq = None
    tx_freq = None
    lineitemlist = []
    textItemList = []
    connected = False
    bandwidth = 0
    bandwidth_mark = []
    worked_list = {}
    text_color = QtGui.QColor(45, 45, 45)
    graphicsView: QGraphicsView = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        appevent.register(appevent.CallChanged, self.event_call_changed)
        appevent.register(appevent.ActiveContest, self.event_contest_status)
        appevent.register(appevent.FindDx, self.event_find_dx)
        appevent.register(appevent.MarkDx, self.event_mark_dx)
        appevent.register(appevent.SpotDx, self.event_spot_dx)
        appevent.register(appevent.RadioState, self.event_radio_state)
        appevent.register(appevent.BandmapSpotNext, self.event_tune_next_spot)
        appevent.register(appevent.BandmapSpotPrev, self.event_tune_prev_spot)
        appevent.register(appevent.WorkedList, self.event_worked)

        uic.loadUi(fsutils.APP_DATA_PATH / "bandmap.ui", self)
        self.settings = self.get_settings()
        self.agetime = self.clear_spot_olderSpinBox.value()
        self.clear_spot_olderSpinBox.valueChanged.connect(self.spot_aging_changed)
        self.clearButton.clicked.connect(self.clear_spots)
        self.zoominButton.clicked.connect(self.dec_zoom)
        self.zoomoutButton.clicked.connect(self.inc_zoom)
        self.connectButton.clicked.connect(self.connect)
        self.spots = Database()
        self.bandmap_scene = QtWidgets.QGraphicsScene()
        self.socket = QtNetwork.QTcpSocket()
        self.socket.readyRead.connect(self.receive)
        self.socket.connected.connect(self.maybeconnected)
        self.socket.disconnected.connect(self.disconnected)
        self.socket.errorOccurred.connect(self.socket_error)
        self.bandmap_scene.clear()
        self.bandmap_scene.setFocusOnTouch(False)
        self.bandmap_scene.selectionChanged.connect(self.spot_clicked)
        self.freq = 0.0
        self.keepRXCenter = False
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.update_station_timer)
        self.update_timer.start(UPDATE_INTERVAL)
        self.update()

        appevent.emit(appevent.GetWorkedList())
        appevent.emit(appevent.GetActiveContest())


    def get_settings(self) -> dict:
        """Get the settings."""
        if os.path.exists(fsutils.CONFIG_FILE):
            with open(fsutils.CONFIG_FILE, "rt", encoding="utf-8") as file_descriptor:
                self.settings = loads(file_descriptor.read())
                if self.settings.get("darkmode"):
                    self.text_color = QtGui.QColor(228, 231, 235)
                else:
                    self.text_color = QtGui.QColor(20, 20, 20)
                return self.settings

    def connect(self):
        """Connect to the cluster."""
        if not self.callsignField.text():
            self.callsignField.setFocus()
            return
        if self.connected is True:
            self.close_cluster()
            return
        # refresh settings
        self.settings = self.get_settings()
        server = self.settings.get("cluster_server", "dxc.nc7j.com")
        port = self.settings.get("cluster_port", 7373)
        logger.info(f"connecting to dx cluster {server} {port}")
        self.socket.connectToHost(server, port)
        self.connectButton.setStyleSheet("color: white;")
        self.connectButton.setText("Connecting")
        self.connected = True

    def event_radio_state(self, event: appevent.RadioState):
        # TODO if multiple band maps, check to make sure this bandmap window is the one tracking the vfo

        self.set_band(ham_utility.getband(str(event.vfoa_hz)) + "m", False)
        try:
            if self.rx_freq != float(event.vfoa_hz) / 1000000:
                self.rx_freq = float(event.vfoa_hz) / 1000000
                self.tx_freq = self.rx_freq
                self.center_on_rxfreq()
        except ValueError:
            logger.debug(f"vfo value error {event.vfoa_hz}")


        self.bandwidth = event.bandwith_hz if event.bandwith_hz is not None else 0
        step, _ = self.determine_step_digits()
        self.drawTXRXMarks(step)


    def event_tune_next_spot(self, event: appevent.BandmapSpotNext):
        if self.rx_freq:
            spot = self.spots.get_next_spot(self.rx_freq + 0.000001, self.currentBand.end)
            if spot:
                appevent.emit(appevent.Tune( spot.get("freq", self.rx_freq) * 1_000_000, spot.get("callsign", "")))

    def event_tune_prev_spot(self, event: appevent.BandmapSpotPrev):
        if self.rx_freq:
            spot = self.spots.get_prev_spot(self.rx_freq - 0.000001, self.currentBand.start)
            if spot:
                appevent.emit(appevent.Tune(spot.get("freq", self.rx_freq) * 1_000_000, spot.get("callsign", "")))

    def event_spot_dx(self, event: appevent.SpotDx):
        # cluster expects Mhz
        spotdx = f"dx {event.dx} {event.freq_hz / 1_000_000}"
        self.send_command(spotdx)

    def event_mark_dx(self, event: appevent.MarkDx):
        spot = {
            "ts": "2099-01-01 01:00:00",
            "callsign": event.dx,
            "freq": event.freq_hz / 1_000_000,
            "band": self.currentBand.name,
            "mode": "DX",
            "spotter": event.de,
            "comment": "MARKED",
        }
        self.spots.addspot(spot, erase=True)
        self.update_stations()

    def event_find_dx(self, event: appevent.FindDx):
        spot = self.spots.get_matching_spot(event.dx, self.currentBand.start, self.currentBand.end)
        if spot:
            logger.debug(f"translating spot mhz to hz {spot['freq']} = {spot['freq'] * 1_000_000}")
            appevent.emit(appevent.Tune(spot['freq'] * 1_000_000,  spot.get("callsign", "")))

    def event_worked(self, event: appevent.WorkedList):
        self.worked_list = event.worked

    def event_call_changed(self, event: appevent.CallChanged):
        result = None
        if event.call:
            # can be empty
            result = self.spots.get_like_calls(event.call)
        appevent.emit(appevent.CheckSpots(result))

    def event_contest_status(self, event: appevent.ActiveContest):
        # pre-fill the cluster login station name for convenience
        if not self.callsignField.text():
            self.callsignField.setText(event.operator.upper())


    def spot_clicked(self):
        items = self.bandmap_scene.selectedItems()
        if len(items) == 1 and items[0].property("freq"):
            appevent.emit(appevent.Tune(items[0].property("freq") * 1_000_000, items[0].toPlainText().split()[0]))

    def update_station_timer(self):
        """doc"""
        self.update_stations()

    def update(self):

        try:
            self.update_timer.setInterval(UPDATE_INTERVAL)
        except AttributeError:
            ...
        self.clear_all_callsign_from_scene()
        self.clear_freq_mark(self.rxMark)
        self.clear_freq_mark(self.txMark)
        self.clear_freq_mark(self.bandwidth_mark)
        self.bandmap_scene.clear()

        step, _digits = self.determine_step_digits()
        steps = int(round((self.currentBand.end - self.currentBand.start) / step))
        self.graphicsView.setFixedSize(330, steps * PIXELSPERSTEP + 30)
        self.graphicsView.setScene(self.bandmap_scene)
        for i in range(steps):  # Draw tickmarks
            length = 10
            if i % 5 == 0:
                length = 15
            self.bandmap_scene.addLine(
                0,
                i * PIXELSPERSTEP,
                length,
                i * PIXELSPERSTEP,
                QtGui.QPen(self.text_color),
            )
            if i % 5 == 0:  # Add Frequency
                freq = self.currentBand.start + step * i
                text = f"{freq:.3f}"
                textItem = self.bandmap_scene.addText(text)
                textItem.setDefaultTextColor(self.text_color)
                textItem.setPos(
                    -(textItem.boundingRect().width()), # + 10,
                    i * PIXELSPERSTEP - (textItem.boundingRect().height() / 2),
                )

        freq = self.currentBand.end + step * steps
        endFreqDigits = f"{freq:.3f}"
        self.bandmap_scene.setSceneRect(
            160 - (len(endFreqDigits) * PIXELSPERSTEP), 0, 0, steps * PIXELSPERSTEP + 20
        )

        self.drawTXRXMarks(step)
        self.update_stations()

    def inc_zoom(self):
        """doc"""
        self.zoom += 1
        self.zoom = min(self.zoom, 7)
        self.update()
        self.center_on_rxfreq()

    def dec_zoom(self):
        """doc"""
        self.zoom -= 1
        self.zoom = max(self.zoom, 1)
        self.update()
        self.center_on_rxfreq()

    def drawTXRXMarks(self, step):
        """doc"""
        if self.rx_freq:
            self.clear_freq_mark(self.bandwidth_mark)
            self.clear_freq_mark(self.rxMark)
            self.draw_bandwidth(
                self.rx_freq, step, QtGui.QColor(30, 30, 180, 180), self.bandwidth_mark
            )
            self.drawfreqmark(
                self.rx_freq, step, QtGui.QColor(30, 180, 30, 180), self.rxMark
            )

    def Freq2ScenePos(self, freq: float):
        """doc"""
        if not freq or freq < self.currentBand.start or freq > self.currentBand.end:
            return QtCore.QPointF()
        step, _digits = self.determine_step_digits()
        ret = QtCore.QPointF(
            0,
            (
                (Decimal(str(freq)) - Decimal(str(self.currentBand.start)))
                / Decimal(str(step))
            )
            * PIXELSPERSTEP,
        )
        return ret

    def center_on_rxfreq(self):
        """doc"""
        freq_pos = self.Freq2ScenePos(self.rx_freq).y()
        # self.graphicsView.verticalScrollBar().setSliderPosition(
        #     int(freq_pos - (self.height() / 2) + 80)
        # )
        self.scrollArea.verticalScrollBar().setValue(
            int(freq_pos - (self.height() / 2) + 80)
        )
        # This does not work... Have no idea why.
        # anim = QtCore.QPropertyAnimation(
        #     self.scrollArea.verticalScrollBar(), "value".encode()
        # )
        # anim.setDuration(300)
        # anim.setStartValue(self.scrollArea.verticalScrollBar().value())
        # anim.setEndValue(int(freq_pos - (self.height() / 2) + 80))
        # anim.start(QtCore.QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    def drawfreqmark(self, freq, _step, color, currentPolygon) -> None:
        """doc"""

        self.clear_freq_mark(currentPolygon)
        # do not show the freq mark if it is outside the bandmap
        if freq < self.currentBand.start or freq > self.currentBand.end:
            return

        Yposition = self.Freq2ScenePos(freq).y()

        poly = QtGui.QPolygonF()

        poly.append(QtCore.QPointF(11, Yposition))
        poly.append(QtCore.QPointF(0, Yposition - 7))
        poly.append(QtCore.QPointF(0, Yposition + 7))
        pen = QtGui.QPen()
        brush = QtGui.QBrush(color)
        currentPolygon.append(self.bandmap_scene.addPolygon(poly, pen, brush))

    def draw_bandwidth(self, freq, _step, color, currentPolygon) -> None:
        """bandwidth"""
        logger.debug(f"mark:{currentPolygon} f:{freq} b:{self.bandwidth}")
        self.clear_freq_mark(currentPolygon)
        if freq < self.currentBand.start or freq > self.currentBand.end:
            return
        if freq and self.bandwidth:
            # color = QtGui.QColor(30, 30, 180)
            bw_start = Decimal(str(freq)) - (
                (Decimal(str(self.bandwidth)) / 2) / 1000000
            )
            bw_end = Decimal(str(freq)) + ((Decimal(str(self.bandwidth)) / 2) / 1000000)

            #logger.debug(f"s:{bw_start} e:{bw_end}")
            Yposition_neg = self.Freq2ScenePos(bw_start).y()
            Yposition_pos = self.Freq2ScenePos(bw_end).y()
            poly = QtGui.QPolygonF()
            poly.append(QtCore.QPointF(5, Yposition_neg))
            poly.append(QtCore.QPointF(10, Yposition_neg))
            poly.append(QtCore.QPointF(10, Yposition_pos))
            poly.append(QtCore.QPointF(5, Yposition_pos))
            pen = QtGui.QPen()
            brush = QtGui.QBrush(color)
            currentPolygon.append(self.bandmap_scene.addPolygon(poly, pen, brush))

    def update_stations(self):
        """doc"""
        self.update_timer.setInterval(UPDATE_INTERVAL)
        if not self.isVisible():
            return
        self.clear_all_callsign_from_scene()
        self.spot_aging()
        step, _digits = self.determine_step_digits()

        result = self.spots.getspotsinband(self.currentBand.start, self.currentBand.end)
        #logger.debug(f"{len(result)} spots in range {self.currentBand.start} - {self.currentBand.end}")

        if result:
            min_y = 0.0
            for items in result:
                pen_color = self.text_color
                if items.get("comment") == "MARKED":
                    pen_color = QtGui.QColor(47, 47, 255)
                if items.get("callsign") in self.worked_list:
                    call_bandlist = self.worked_list.get(items.get("callsign"))
                    if self.currentBand.altname in call_bandlist:
                        pen_color = QtGui.QColor(255, 47, 47)
                freq_y = (
                    (items.get("freq") - self.currentBand.start) / step
                ) * PIXELSPERSTEP
                text_y = max(min_y + 5, freq_y)
                self.lineitemlist.append(
                    self.bandmap_scene.addLine(
                        22, freq_y, 45, text_y, QtGui.QPen(pen_color)
                    )
                )
                text = self.bandmap_scene.addText(
                    items.get("callsign")
                    + " " + timeutils.time_ago(items.get("ts"))
                    + " " + items.get("comment")[:40]
                )
                text.setHtml("<span style='font-family: JetBrains Mono;'>"
                    + items.get("callsign") + "</span> - "
                    + timeutils.time_ago(items.get("ts"))
                    + " - " + items.get("comment")[:40])
                text.document().setDocumentMargin(0)

                text.setPos(50, text_y - (text.boundingRect().height() / 2))
                text.setFlags(
                    QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
                    | QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
                    | text.flags()
                )
                text.setProperty("freq", items.get("freq"))
                text.setToolTip(items.get("callsign")
                                + f" - " + '{0:.5f}'.format(items.get("freq"))
                                + " - " + items.get("ts")
                                + " - " + items.get("comment"))
                text.setDefaultTextColor(pen_color)
                min_y = text_y + text.boundingRect().height() / 2
                self.textItemList.append(text)

    def determine_step_digits(self):
        """doc"""
        return_zoom = {
            1: (0.0001, 4),
            2: (0.00025, 4),
            3: (0.0005, 4),
            4: (0.001, 3),
            5: (0.0025, 3),
            6: (0.005, 3),
            7: (0.01, 2),
        }
        step, digits = return_zoom.get(self.zoom, (0.0001, 4))

        if self.currentBand.start >= 28.0 and self.currentBand.start < 420.0:
            step = step * 10
            return (step, digits)

        if self.currentBand.start >= 420.0 and self.currentBand.start < 2300.0:
            step = step * 100

        return (step, digits)

    def set_band(self, band: str, savePrevBandZoom: bool) -> None:
        """Change band being shown."""
        logger.debug("%s", f"{band} {savePrevBandZoom}")
        if band != self.currentBand.name:
            if savePrevBandZoom:
                self.saveCurrentZoom()
            self.currentBand = Band(band)
            self.update()

    def spot_aging(self) -> None:
        """Delete spots older than age time."""
        if self.agetime:
            self.spots.delete_spots(self.agetime)

    def clear_all_callsign_from_scene(self) -> None:
        """Remove callsigns from the scene."""
        for items in self.textItemList:
            self.bandmap_scene.removeItem(items)
        self.textItemList.clear()
        for items in self.lineitemlist:
            self.bandmap_scene.removeItem(items)
        self.lineitemlist.clear()

    def clear_freq_mark(self, currentPolygon) -> None:
        """Remove frequency marks from the scene."""
        if currentPolygon:
            for mark in currentPolygon:
                self.bandmap_scene.removeItem(mark)
        currentPolygon.clear()

    def receive(self) -> None:
        """Process waiting bytes"""
        while self.socket.bytesAvailable():
            data = self.socket.readLine(1000)
            data = str(data, "utf-8").strip()

            if "login:" in data or "call:" in data or "callsign:" in data:
                self.send_command(self.callsignField.text())
                self.send_command(self.settings.get("cluster_filter", ""))
                self.send_command("set dx extension Section")
                self.send_command(
                    "set dx mode " + self.settings.get("cluster_mode", "OPEN")
                )
                return
            if "DX de" in data:
                parts = data.split()
                spotter = parts[2]
                freq = parts[3]
                dx = parts[4]
                _time = parts[-1]
                comment = " ".join(parts[5:-1])
                # spot = DxSpot()
                spot = {}
                spot["ts"] = datetime.now(timezone.utc).isoformat(" ")[:19]
                spot["callsign"] = dx
                spot["spotter"] = spotter
                spot["comment"] = comment
                try:
                    spot["freq"] = float(freq) / 1000
                    self.spots.addspot(spot)
                except ValueError:
                    logger.debug(f"couldn't parse freq from datablock {data}")
                logger.debug(f"{spot}")
                return
            if self.callsignField.text().upper() in data:
                self.connectButton.setStyleSheet("color: green;")
                self.connectButton.setText("Connected")
                logger.debug(f"callsign login acknowledged {data}")

    def maybeconnected(self) -> None:
        """Update visual state of the connect button."""
        self.connectButton.setStyleSheet("color: yellow;")
        self.connectButton.setText("Connecting")

    def socket_error(self) -> None:
        """Oopsie"""
        logger.warning("An Error occurred.")

    def disconnected(self) -> None:
        """Called when socket is disconnected."""
        self.connected = False
        self.connectButton.setStyleSheet("color: red;")
        self.connectButton.setText("Closed")

    def send_command(self, cmd: str) -> None:
        """Send a command to the cluster."""
        cmd += "\r\n"
        tosend = bytes(cmd, encoding="ascii")
        logger.debug("%s", f"{tosend}")
        if self.socket:
            if self.socket.isOpen():
                self.socket.write(tosend)

    def clear_spots(self) -> None:
        """Delete all spots from the database."""
        self.spots.delete_spots(0)

    def spot_aging_changed(self) -> None:
        """Called when spot aging spinbox is changed."""
        self.agetime = self.clear_spot_olderSpinBox.value()

    def showContextMenu(self) -> None:
        """doc string for the linter"""

    def close_cluster(self) -> None:
        """Close socket connection"""
        if self.socket and self.socket.isOpen():
            logger.info("Closing dx cluster connection")
            self.socket.close()
            self.connected = False
            self.connectButton.setStyleSheet("color: red;")
            self.connectButton.setText("Closed")

    def closeEvent(self, _event: QtGui.QCloseEvent) -> None:
        """Triggered when instance closes."""
        self.close_cluster()

