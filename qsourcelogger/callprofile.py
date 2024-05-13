#!/usr/bin/env python3

# pylint: disable=no-name-in-module, unused-import, no-member, invalid-name, logging-fstring-interpolation, c-extension-no-member

import logging
import typing

from PyQt6 import uic, QtNetwork, QtGui
from PyQt6.QtCore import QUrl, Qt, QSize, QBuffer
from PyQt6.QtGui import QImage, QPixmap, QDesktopServices, QIcon
from PyQt6.QtNetwork import QNetworkReply, QNetworkRequest, QNetworkDiskCache
from PyQt6.QtWidgets import QDockWidget, QLabel, QStyle

import qsourcelogger.fsutils as fsutils
from qsourcelogger.lib import event
from qsourcelogger.lib.ham_utility import get_call_base
from qsourcelogger.qtcomponents.DockWidget import DockWidget
from qsourcelogger.qtcomponents.SvgIcon import SvgIcon

logger = logging.getLogger(__name__)


class ScaledLabel(QLabel):
    """Basic image-in-a-label which will scale to it's changing dimensions"""
    pixmap: QPixmap
    icon: QIcon
    external_url: str

    def __init__(self, *args, **kwargs):
        self.pixmap = None
        super().__init__(*args, **kwargs)
        self.setMinimumHeight(1)
        self.setMinimumWidth(1)

    def setPixmap(self, pixmap: QPixmap, size: QSize):
        self.pixmap = pixmap
        if pixmap:
            scaled = self.pixmap.scaled(size.boundedTo(QSize(size.width() - 2, size.height())),
                                        Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            super().setPixmap(scaled)
            # center label in parent. vertical centering is handled automatically widget layout
            if scaled.width() < size.width():
                h_gap = int((size.width() - scaled.width()) / 2)
                self.setContentsMargins(h_gap, 0, h_gap, 0)
            else:
                self.setContentsMargins(0, 0, 0, 0)


    def clear(self):
        self.pixmap = None
        self.external_url = None
        self.setContentsMargins(0, 0, 0, 0)
        super().clear()

    def resizeEvent(self, event: typing.Optional[QtGui.QResizeEvent]) -> None:
        self.setPixmap(self.pixmap, event.size())
        super().resizeEvent(event)

    def set_external_url(self, url: str):
        self.external_url = url

    def mousePressEvent(self, ev: typing.Optional[QtGui.QMouseEvent]) -> None:
        if self.external_url and self.pixmap:
            QDesktopServices.openUrl(QUrl(self.external_url))
        super().mousePressEvent(ev)


class ExternalCallProfileWindow(DockWidget):
    imageLabel: ScaledLabel
    network_access_manager = QtNetwork.QNetworkAccessManager()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        uic.loadUi(fsutils.APP_DATA_PATH / "call_external_profile.ui", self)

        event.register(event.ExternalLookupResult, self.event_external_lookup)
        event.register(event.CallChanged, self.event_call_changed)
        self.network_access_manager.finished.connect(self.handle_image)
        self.imageLabel = ScaledLabel()
        self.setWidget(self.imageLabel)
        self.reset_image()

        disk_cache = QNetworkDiskCache(self)
        disk_cache.setCacheDirectory(str(fsutils.USER_DATA_PATH / 'profile_image_cache'))
        disk_cache.setMaximumCacheSize(10 * 1024 * 1024)
        self.network_access_manager.setCache(disk_cache)

    def reset_image(self):
        self.imageLabel.clear()
        self.imageLabel.setPixmap(SvgIcon('image_polaroid').rotate(10)
                                  .get_icon().pixmap(self.frameSize(), self.devicePixelRatio()), self.frameSize())
        self.imageLabel.setToolTip(None)

    def event_external_lookup(self, e: event.ExternalLookupResult):
        """Upon successful external callsign db lookup, populate the station profile information"""
        if get_call_base(e.result.call) != get_call_base(self.call):
            # make sure the station in the external data is still the active qso callsign
            return
        if e.result.profile_image:
            logger.debug(f"fetching {e.result.call} image url {e.result.profile_image}")
            self.imageLabel.clear()
            self.network_access_manager.get(QNetworkRequest(QUrl(e.result.profile_image)))
            self.setWindowTitle(f"{e.result.call} Profile")
            if 'qrz' in e.result.profile_image:
                self.setWindowTitle(f"{e.result.call} QRZ Profile")
                self.imageLabel.set_external_url(f'https://www.qrz.com/db/{e.result.call}')
            else:
                self.setWindowTitle(f"{e.result.call} {QUrl(e.result.profile_image).host()} Profile")

    def event_call_changed(self, e: event.CallChanged):
        self.call = e.call
        self.reset_image()
        self.setWindowTitle(f"Station Profile")


    def handle_image(self, reply: QNetworkReply):
        """handle image data download (display it)"""
        er = reply.error()
        reply.deleteLater()
        if er != QtNetwork.QNetworkReply.NetworkError.NoError:
            logger.error(reply.errorString())
        else:
            raw_image = reply.readAll()
            image = QImage()
            image.loadFromData(raw_image)
            self.imageLabel.setPixmap(QPixmap(image), self.frameSize())
            self.imageLabel.setToolTip(
                f"<img src='data:{reply.header(QNetworkRequest.KnownHeaders.ContentTypeHeader)};base64,{bytes(raw_image.toBase64()).decode()}'"
                f"{' width=1000' if image.width() > 1000 else ''}/>")

