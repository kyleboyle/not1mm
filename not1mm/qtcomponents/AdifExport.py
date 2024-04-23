import logging
import os

from PyQt6 import QtWidgets, uic
from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QFileDialog, QTableWidget, QLabel, QRadioButton

from not1mm import fsutils
from not1mm.lib.hamutils.adif import ADIWriter, ADXWriter
from not1mm.model import Contest, QsoLog, adapters

logger = logging.getLogger(__name__)

class ExportWorker(QThread):

    table_preview: QTableWidget

    def __init__(self, contest: Contest, file: str, is_xml: bool):
        super().__init__()
        self.file = file
        self.is_xml = is_xml
        self.contest = contest
        self.result = []

    def run(self):
        with open(self.file, 'wb') as f:
            if self.is_xml:
                self.process_import_list(ADXWriter(f))
            else:
                self.process_import_list(ADIWriter(f))

    def process_import_list(self, writer):
        for qso in QsoLog.select().where(QsoLog.fk_contest == self.contest):
            converted = adapters.convert_qso_to_adif(qso)
            writer.add_qso(**converted)
        writer.close()

class AdifExport(QtWidgets.QDialog):

    label_success: QLabel
    filename: str = None
    radio_adi: QRadioButton
    def __init__(self, contest: Contest, parent=None) -> None:
        super().__init__(parent)

        uic.loadUi(fsutils.APP_DATA_PATH / 'AdifExport.ui', self)
        self.contest = contest
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
        self.radio_adi.clicked.connect(self.file_type_adi)
        self.radio_xml.clicked.connect(self.file_type_xml)

    def choose_file(self):
        self.label_success.setVisible(False)
        current_file = self.file_path.text()
        if not current_file:
            current_file = fsutils.USER_DATA_PATH
        filename, filter = QFileDialog.getSaveFileName(
            None,
            "Export ADIF Log File",
            str(current_file),
            "adif (*.adi *.adx)",
            options=QFileDialog.Option.DontUseNativeDialog,)

        self.button_export.setEnabled(False)
        self.label_success.setVisible(False)
        if filename:
            self.filename = filename
            self.filter = filter
            self.file_path.setText(self.filename)
            if filename.endswith('adi'):
                self.radio_adi.setChecked(True)
            elif filename.endswith('adx'):
                self.radio_xml.setChecked(True)

        if self.filename:
            self.button_export.setEnabled(True)
            self.button_export.setFocus()

    def file_type_adi(self):
        self.label_success.setVisible(False)
        if self.filename:
            self.filename = self.filename[:self.filename.rfind('.')] + '.adi'
            self.file_path.setText(self.filename)

    def file_type_xml(self):
        self.label_success.setVisible(False)
        if self.filename:
            self.filename = self.filename[:self.filename.rfind('.')] + '.adx'
            self.file_path.setText(self.filename)

    def start_export(self):
        if self.filename:
            logger.info(f"Exporting qsos for contest "
                        f"{self.contest.id}) {self.contest.fk_contest_meta.display_name} [start: "
                        f"{self.contest.start_date.date()}] to file name {self.filename}")

            self.export_thread = ExportWorker(self.contest, self.filename, self.radio_xml.isChecked())
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


