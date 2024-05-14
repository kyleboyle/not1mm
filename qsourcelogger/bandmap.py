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
from datetime import timezone
from decimal import Decimal
from json import loads

from PyQt6 import QtCore, QtGui, QtWidgets, uic, QtNetwork
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtWidgets import QGraphicsView

import qsourcelogger.fsutils as fsutils
import qsourcelogger.lib.event as appevent
from qsourcelogger.lib import timeutils, ham_utility
from qsourcelogger.model.inmemory import *
from qsourcelogger.qtcomponents.DockWidget import DockWidget

logger = logging.getLogger(__name__)

PIXELSPERSTEP = 10
UPDATE_INTERVAL = 2000

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

    @classmethod
    def getBandFreqLimits(cls, freq_hz):
        freq_mz = freq_hz / 1_000_000
        for band_limits in cls.bands.values():
            if band_limits[0] <= freq_mz <= band_limits[1]:
                return band_limits
        return None

class BandMapWindow(DockWidget):
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
    # TODO pull worked calls from db, maintain list with app events
    worked_list = {}
    text_color = QtGui.QColor(45, 45, 45)
    graphicsView: QGraphicsView = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        appevent.register(appevent.GetActiveContestResponse, self.event_contest_status)
        appevent.register(appevent.FindDx, self.event_find_dx)
        appevent.register(appevent.MarkDx, self.event_mark_dx)
        appevent.register(appevent.SpotDx, self.event_spot_dx)
        appevent.register(appevent.RadioState, self.event_radio_state)
        appevent.register(appevent.BandmapSpotNext, self.event_tune_next_spot)
        appevent.register(appevent.BandmapSpotPrev, self.event_tune_prev_spot)

        uic.loadUi(fsutils.APP_DATA_PATH / "bandmap.ui", self)
        self.settings = self.get_settings()
        self.clear_spot_olderSpinBox.setValue(self.settings.get("bandmap_spot_age_minutes", 2))
        self.agetime = self.clear_spot_olderSpinBox.value()
        self.clear_spot_olderSpinBox.valueChanged.connect(self.spot_aging_changed)
        self.clearButton.clicked.connect(self.clear_spots)
        self.zoominButton.clicked.connect(self.dec_zoom)
        self.zoomoutButton.clicked.connect(self.inc_zoom)
        self.connectButton.clicked.connect(self.connect)

        self.bandmap_scene = QtWidgets.QGraphicsScene()
        self.socket = QtNetwork.QTcpSocket()
        self.socket.readyRead.connect(self.receive)
        self.socket.connected.connect(self.maybeconnected)
        self.socket.disconnected.connect(self.disconnected)
        self.socket.errorOccurred.connect(self.socket_error)
        self.bandmap_scene.clear()
        self.bandmap_scene.setFocusOnTouch(False)
        self.bandmap_scene.selectionChanged.connect(self.spot_clicked)

        self.graphicsView.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.graphicsView.setMinimumWidth(200)

        self.freq = 0.0
        self.keepRXCenter = False
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.update_station_timer)
        self.update_timer.start(UPDATE_INTERVAL)
        self.update()

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
        self.clear_spot_olderSpinBox.setValue(self.settings.get("bandmap_spot_age_minutes", 2))

    def event_radio_state(self, event: appevent.RadioState):
        # TODO when/if multiple band maps, check to make sure this bandmap window is the one tracking the vfo

        self.set_band(ham_utility.getband(str(event.state.vfotx_hz or 0)) + "m", False)
        try:
            if self.rx_freq != float(event.state.vfotx_hz or 0) / 1_000_000:
                self.rx_freq = float(event.state.vfotx_hz or 0) / 1_000_000
                self.tx_freq = self.rx_freq
                self.center_on_rxfreq()
        except ValueError:
            logger.debug(f"vfo value error {event.state.vfotx_hz}")

        self.bandwidth = event.state.bandwidth_hz if event.state.bandwidth_hz is not None else 0
        step, _ = self.determine_step_digits()
        self.drawTXRXMarks(step)

    def event_tune_next_spot(self, event: appevent.BandmapSpotNext):
        if self.rx_freq:
            spot = Spot.select().where(
                Spot.freq_hz.between(int(self.rx_freq  * 1_000_000) + 1, self.currentBand.end * 1_000_000))\
                .orderby(Spot.freq_hz).get()
            if spot:
                appevent.emit(appevent.Tune(spot.freq_hz, spot.callsign))

    def event_tune_prev_spot(self, event: appevent.BandmapSpotPrev):
        if self.rx_freq:
            spot = Spot.select().where(
                Spot.freq_hz.between(self.currentBand.start * 1_000_000, int(self.rx_freq  * 1_000_000) - 1))\
                .order_by(Spot.freq_hz.desc()).get()
            if spot:
                appevent.emit(appevent.Tune(spot.freq_hz, spot.callsign))

    def event_spot_dx(self, event: appevent.SpotDx):
        # cluster expects Mhz or khz
        spotdx = f"dx {event.dx} {event.freq_hz / 1_000_000} {event.comment}"
        if self.connected:
            self.send_command(spotdx)
        else:
            logger.warning(f"dx cluster not connected, ignoring spot {spotdx}")

    def event_mark_dx(self, event: appevent.MarkDx):
        Spot(ts=datetime.utcnow() + timedelta(days=2),
             callsign=event.dx,
             freq_hz=event.freq_hz,
             mode="DX",
             spotter=event.de,
             comment="MARKED"
             ).save()
        self.update_stations()

    def event_find_dx(self, event: appevent.FindDx):
        spot = Spot.select().where(
            (Spot.callsign == event.dx)
            & (Spot.freq_hz.between(self.currentBand.start * 1_000_000, self.currentBand.end * 1_000_000))).get()
        if spot:
            appevent.emit(appevent.Tune(spot.freq_hz,  spot.callsign))

    def event_contest_status(self, event: appevent.GetActiveContestResponse):
        # pre-fill the cluster login station name for convenience
        if not self.callsignField.text() and event.operator:
            self.callsignField.setText(event.operator.upper())

    def spot_clicked(self):
        items = self.bandmap_scene.selectedItems()
        if len(items) == 1 and items[0].property("freq_hz"):
            appevent.emit(appevent.Tune(items[0].property("freq_hz"), items[0].toPlainText().split()[0]))

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
        self.graphicsView.setFixedHeight(steps * PIXELSPERSTEP + 30)
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
                text_item = self.bandmap_scene.addText(text)
                text_item.setDefaultTextColor(self.text_color)
                text_item.setPos(-(text_item.boundingRect().width()),
                                 i * PIXELSPERSTEP - (text_item.boundingRect().height() / 2))

        scene_rect = self.bandmap_scene.itemsBoundingRect()
        scene_rect.setY(0)
        self.bandmap_scene.setSceneRect(scene_rect)
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

        self.scrollArea.verticalScrollBar().setValue(
            int(freq_pos - (self.height() / 2) + 80)
        )

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

        result: list[Spot] = Spot.select().where(Spot.freq_hz.between(
            self.currentBand.start * 1_000_000, self.currentBand.end * 1_000_000))\
            .order_by(Spot.freq_hz.asc()).limit(200)
        #logger.debug(f"{len(result)} spots in range {self.currentBand.start} - {self.currentBand.end}")

        if result:
            min_y = 0.0
            for spot in result:
                pen_color = self.text_color
                if spot.comment == "MARKED":
                    pen_color = QtGui.QColor(47, 47, 255)
                # TODO there should be a better way to properly work the contest dupe settings into the colors here
                if spot.callsign in self.worked_list:
                    call_bandlist = self.worked_list.get(spot.callsign)
                    if self.currentBand.altname in call_bandlist:
                        pen_color = QtGui.QColor(255, 47, 47)
                freq_y = (
                    (spot.freq_hz/1_000_000 - self.currentBand.start) / step
                ) * PIXELSPERSTEP
                text_y = max(min_y + 5, freq_y)
                self.lineitemlist.append(
                    self.bandmap_scene.addLine(
                        22, freq_y, 45, text_y, QtGui.QPen(pen_color)
                    )
                )
                text = self.bandmap_scene.addText(spot.callsign) # overwritten with html
                text.setHtml("<span style='font-family: JetBrains Mono;'>"
                    + spot.callsign + "</span> - "
                    + timeutils.time_ago(spot.ts)
                    + " - " + spot.comment[:40])
                text.document().setDocumentMargin(0)

                text.setPos(50, text_y - (text.boundingRect().height() / 2))
                text.setFlags(
                    QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
                    | QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
                    | text.flags()
                )
                text.setProperty("freq_hz", spot.freq_hz)
                text.setToolTip(spot.callsign
                                + f" - " + '{0:.5f}'.format(spot.freq_hz / 1_000_000)
                                + " - " + str(spot.ts.strftime("%H:%M:%SZ"))
                                + " - " + spot.comment)
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
            Spot.delete_before(self.agetime)

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

                try:
                    spot = Spot(ts=datetime.utcnow(),
                         callsign=dx,
                         freq_hz=int(float(freq) * 1000),
                         mode="DX",
                         spotter=spotter,
                         comment=comment
                         )
                    self.save_spot(spot)
                    logger.debug(spot)
                except ValueError:
                    logger.debug(f"couldn't parse freq from datablock {data}")
                return
            if self.callsignField.text().upper() in data:
                self.connectButton.setStyleSheet("color: green;")
                self.connectButton.setText("Connected")
                logger.debug(f"callsign login acknowledged {data}")

    def save_spot(self, spot: Spot):
        band_limits = Band.getBandFreqLimits(spot.freq_hz)
        if band_limits:
            # remove existing spots for same call on same band
            Spot.delete().where(
                (Spot.callsign == spot.callsign)
                & (Spot.freq_hz.between(band_limits[0] * 1_000_000, band_limits[1] * 1_000_000))
            ).execute()
        spot.save()

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
        Spot.delete_before(0)

    def spot_aging_changed(self) -> None:
        """Called when spot aging spinbox is changed."""
        self.agetime = self.clear_spot_olderSpinBox.value()
        fsutils.write_settings({"bandmap_spot_age_minutes": self.agetime})

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

