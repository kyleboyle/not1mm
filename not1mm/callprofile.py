#!/usr/bin/env python3

# pylint: disable=no-name-in-module, unused-import, no-member, invalid-name, logging-fstring-interpolation, c-extension-no-member

import logging
import typing

from PyQt6 import uic, QtNetwork, QtGui
from PyQt6.QtCore import QUrl, Qt, QSize, QBuffer
from PyQt6.QtGui import QImage, QPixmap, QDesktopServices
from PyQt6.QtNetwork import QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import QDockWidget, QLabel, QStyle

import not1mm.fsutils as fsutils
from not1mm.lib import event
from not1mm.qtplugins.DockWidget import DockWidget

logger = logging.getLogger(__name__)


class ScaledLabel(QLabel):
    """Basic image-in-a-label which will scale to it's changing dimensions"""
    pixmap: QPixmap
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
            # center label in parent
            self.setMargin(0)
            if scaled.width() < self.parent().width() - 5:
                self.setContentsMargins(int((self.parent().width() - scaled.width() + 1) / 2),
                    0,
                    int((self.parent().width() - scaled.width() + 1) / 2),
                    0)

    def clear(self):
        self.pixmap = None
        self.external_url = None
        super().clear()
        self.setPixmap(QPixmap(str(fsutils.APP_DATA_PATH / 'profile_placeholder.png')), self.size())

    def resizeEvent(self, event: typing.Optional[QtGui.QResizeEvent]) -> None:
        logger.debug(f"resizeEvent {event.size()}")
        self.setPixmap(self.pixmap, event.size())

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
        self.imageLabel.clear()

    def event_external_lookup(self, e: event.ExternalLookupResult):
        """Upon successful external callsign db lookup, populate the station profile information"""
        image_url = e.result.source_result.get('image', None)
        if image_url:
            logger.debug(f"fetching {e.result.call} image url {image_url}")
            self.imageLabel.clear()
            self.network_access_manager.get(QNetworkRequest(QUrl(image_url)))
            self.setWindowTitle(f"{e.result.call} Profile")
            if 'qrz' in image_url:
                self.setWindowTitle(f"{e.result.call} QRZ Profile")
                self.imageLabel.set_external_url(f'https://www.qrz.com/db/{e.result.call}')

    def event_call_changed(self, e: event.CallChanged):
        self.imageLabel.clear()
        self.imageLabel.setToolTip(None)
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
            logger.debug(f"size before set pixmap {self.size()}, imagelabel {self.imageLabel.size()}")
            self.imageLabel.setPixmap(QPixmap(image), self.size())
            logger.debug(f"size after set pixmap {self.size()}, imagelabel {self.imageLabel.size()}")
            self.imageLabel.setToolTip(
                f"<img src='data:{reply.header(QNetworkRequest.KnownHeaders.ContentTypeHeader)};base64,{bytes(raw_image.toBase64()).decode()}'"
                f"{' width=1000' if image.width() > 1000 else ''}/>")

