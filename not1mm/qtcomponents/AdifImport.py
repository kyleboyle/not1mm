import json
import logging
import os
import uuid

from PyQt6 import QtWidgets, uic
from PyQt6.QtCore import QThread, Qt
from PyQt6.QtWidgets import QFileDialog, QApplication, QTableWidget, QTableWidgetItem, QLabel

from not1mm import fsutils
from not1mm.lib import event
from not1mm.lib.hamutils.adif import ADIReader, ADXReader
from not1mm.model import Contest, QsoLog, adapters

logger = logging.getLogger(__name__)

class ConversionWorker(QThread):

    table_preview: QTableWidget
    result: list[tuple[str, QsoLog]]
    def __init__(self, file, contest: Contest):
        super().__init__()
        self.file = file
        self.contest = contest
        self.result = []

    def run(self):
        with open(self.file, 'r') as f:
            if self.file.endswith(".adi"):
                self.process_import_list(ADIReader(f))
            elif self.file.endswith(".adx"):
                self.process_import_list(ADXReader(f))

    def process_import_list(self, qso_list):
        for adif in qso_list:
            qso = adapters.convert_adif_to_qso(adif)

            status = 'NEW'
            if qso.id and QsoLog.select().where(QsoLog.id == qso.id).get_or_none():
                status = 'REPLACE(ID)'

            if qso.fk_contest_id is None:
                # make sure the record belongs to a contest
                qso.fk_contest = self.contest

            # check for existing match with significant fields
            result = QsoLog.select().where(QsoLog.call == qso.call)\
                .where(QsoLog.time_on == qso.time_on)\
                .where(QsoLog.band == qso.band)\
                .where((QsoLog.station_callsign == qso.station_callsign) | (QsoLog.operator == qso.operator)) \
                .get_or_none()
            if result:
                # overwrite existing due to matching primary fields
                qso.id = result.id
                status = "REPLACE(MATCHING_FIELDS)"
            self.result.append((status, qso))


class PersistenceWorker(QThread):

    table_preview: QTableWidget
    failed: int = 0
    success: int = 0

    def __init__(self, qsos):
        super().__init__()
        self.qsos = qsos

    def run(self):
        for index, (status, qso) in enumerate(self.qsos):
            is_insert = False
            if not qso.id:
                # set a new id
                qso.id = uuid.uuid4()
                is_insert = True
            try:
                qso.save(force_insert=True if is_insert else False)
                self.success += 1
            except:
                logger.exception("Error inserting qso")
                self.failed += 1


class AdifImport(QtWidgets.QDialog):
    table_preview: QTableWidget
    thread_convert: ConversionWorker
    thread_import: PersistenceWorker
    label_stats: QLabel

    def __init__(self, contest: Contest, parent=None) -> None:
        super().__init__(parent)
        uic.loadUi(fsutils.APP_DATA_PATH / 'AdifImport.ui', self)

        self.contest = contest
        self.label_contest.setText(f"({self.contest.id}) {self.contest.fk_contest_meta.display_name} [start: "
            f"{self.contest.start_date.date()}]")

        self.button_close.clicked.connect(self.close)
        self.button_save.clicked.connect(self.save_import)
        self.button_file.clicked.connect(self.choose_file)

        self.label_stats.setText("")

    def choose_file(self):
        current_file = self.file_path.text()
        if not current_file:
            current_file = fsutils.USER_DATA_PATH
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Import ADIF Log File",
            str(current_file),
            "adif (*.adi *.adx)",
            options=QFileDialog.Option.DontUseNativeDialog | QFileDialog.Option.DontConfirmOverwrite,
        )
        if filename:
            self.table_preview.clear()
            self.file_path.setText(filename)
            self.label_stats.setText("Running...")
            QApplication.processEvents()
            self.thread_convert = ConversionWorker(filename, self.contest)
            self.thread_convert.finished.connect(self.conversion_finished)
            self.thread_convert.start(priority=QThread.Priority.LowPriority)

    def conversion_finished(self):
        sample_size = min(3000, len(self.thread_convert.result))
        self.label_stats.setText(
            f"Record Count: {len(self.thread_convert.result)}, showing sample of {sample_size}")

        self.table_preview.setRowCount(sample_size)
        self.table_preview.setColumnCount(8)
        self.table_preview.setHorizontalHeaderLabels(
            ['status', 'timestamp', 'callsign', 'band', 'mode', 'station', 'operator', 'record id'])
        for index, (status, qso) in enumerate(self.thread_convert.result):
            logger.info(f"{status} {qso.time_on} {qso.call} {qso.band} {qso.station_callsign} {qso.operator} {qso.id}")
            self.table_preview.setItem(index, 0, QTableWidgetItem(status))
            self.table_preview.setItem(index, 1, QTableWidgetItem(str(qso.time_on)))
            self.table_preview.setItem(index, 2, QTableWidgetItem(qso.call))
            self.table_preview.setItem(index, 3, QTableWidgetItem(qso.band))
            self.table_preview.setItem(index, 4, QTableWidgetItem(qso.mode))
            self.table_preview.setItem(index, 5, QTableWidgetItem(qso.station_callsign))
            self.table_preview.setItem(index, 6, QTableWidgetItem(qso.operator))
            self.table_preview.setItem(index, 7, QTableWidgetItem(str(qso.id) if qso.id is not None else '<new>'))
            #logger.debug(f"{json.dumps(qso, sort_keys=True, default=str)}")

        self.table_preview.resizeColumnsToContents()
        self.table_preview.sortByColumn(1, Qt.SortOrder.DescendingOrder)
        self.button_save.setEnabled(True)

    def save_import(self):
        self.button_save.setEnabled(False)
        self.thread_import = PersistenceWorker(self.thread_convert.result)
        self.thread_import.finished.connect(self.import_finished)
        self.thread_import.start(priority=QThread.Priority.LowPriority)

    def import_finished(self):
        self.label_stats.setText(f"Finished. Success # {self.thread_import.success}. Failed # {self.thread_import.failed}")
        event.emit(event.ContestActivated(self.contest))
