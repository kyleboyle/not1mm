import logging
import os

from PyQt6 import QtWidgets, uic
from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QFileDialog, QTableWidget, QLabel, QRadioButton

from qsourcelogger import fsutils
from qsourcelogger.contest.AbstractContest import AbstractContest
from qsourcelogger.lib.hamutils.cabrillo import CabrilloWriter
from qsourcelogger.model import Contest, QsoLog, adapters, Station

logger = logging.getLogger(__name__)

class ExportWorker(QThread):

    table_preview: QTableWidget

    def __init__(self, contest: Contest, contest_plugin: AbstractContest, station: Station, file: str):
        super().__init__()
        self.file = file
        self.contest_plugin = contest_plugin
        self.contest = contest
        self.station = station
        self.result = []

    def run(self):
        with open(self.file, 'wb') as f:
            writer = CabrilloWriter(f)
            headers = self.contest_plugin.cabrillo_headers(self.station)
            for h in headers:
                writer.write_tag(h[0], h[1])

            for qso in self.contest_plugin.contest_qso_select():
                cbr = adapters.convert_qso_to_cabrillo(qso)
                cbr = self.contest_plugin.cabrillo_log(qso, cbr)
                writer.add_qso(cbr.freq, cbr.mode, cbr.timestamp, cbr.operator_call, cbr.rst_sent, cbr.exchange_sent or '',
                               cbr.call, cbr.rst_received, cbr.exchange_received or '', cbr.transmitter_id)
            writer.close()

class CabrilloExport(QtWidgets.QDialog):

    label_success: QLabel
    filename: str = None

    def __init__(self, contest: Contest, contest_plugin: AbstractContest, station: Station, parent=None) -> None:
        super().__init__(parent)

        uic.loadUi(fsutils.APP_DATA_PATH / 'CabrilloExport.ui', self)
        self.contest = contest
        self.contest_plugin = contest_plugin
        self.station = station
        self.label_contest.setText(f"({self.contest.id}) {self.contest.fk_contest_meta.display_name} [start: "
            f"{self.contest.start_date.date()}]")

        self.button_close.clicked.connect(self.close)
        self.button_export.clicked.connect(self.start_export)
        self.button_file.clicked.connect(self.choose_file)
        self.label_success.setVisible(False)
        self.label_qso_count.setText(str(QsoLog.select().where(QsoLog.fk_contest == self.contest).count()))
        self.button_export.setEnabled(False)
        self.button_open_dir.clicked.connect(self.open_dir)
        self.button_open_file.clicked.connect(self.open_file)
        self.button_open_file.setVisible(False)

    def choose_file(self):
        self.label_success.setVisible(False)
        current_file = self.file_path.text()
        if not current_file:
            current_file = fsutils.USER_DATA_PATH
        filename, _ = QFileDialog.getSaveFileName(
            None,
            "Choose Cabrillo File",
            str(current_file),
            "Cabrillo (*.cbr)",
            options=QFileDialog.Option.DontUseNativeDialog,)

        self.button_export.setEnabled(False)
        self.label_success.setVisible(False)
        if filename:
            self.filename = filename
        self.file_path.setText(self.filename)
        if self.filename:
            self.button_export.setEnabled(True)
            self.button_export.setFocus()

    def start_export(self):
        if self.filename:
            logger.info(f"Exporting qsos for contest cabrillo "
                        f"{self.contest.id}) {self.contest.fk_contest_meta.display_name} [start: "
                        f"{self.contest.start_date.date()}] to file name {self.filename}")

            self.export_thread = ExportWorker(self.contest, self.contest_plugin, self.station, self.filename)
            self.export_thread.finished.connect(self.export_finished)
            self.export_thread.start(priority=QThread.Priority.LowPriority)

    def export_finished(self):
        self.label_success.setVisible(True)
        self.button_open_dir.setEnabled(True)
        self.button_open_file.setEnabled(True)

    def open_dir(self):
        fsutils.openFileWithOS(os.path.dirname(self.filename))

    def open_file(self):
        fsutils.openFileWithOS(self.filename)


