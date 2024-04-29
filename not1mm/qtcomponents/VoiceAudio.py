import logging
from pathlib import Path

from PyQt6 import QtWidgets
from PyQt6.QtCore import QThread

from not1mm import fsutils
from not1mm.cat import AbstractCat

logger = logging.getLogger(__name__)

try:
    import sounddevice as sd
except OSError as exception:
    logger.exception("portaudio is not installed")
    sd = None
import soundfile

class VoiceAudio(QThread):
    stop = False
    def __init__(self, say, operator, radio: AbstractCat):
        super().__init__()
        self.say = say
        self.operator = operator
        self.radio = radio
        self.setPriority(QThread.Priority.HighPriority)

    def stop_sound(self):
        self.stop = True
        if sd is not None:
            sd.stop(True)

    def run(self):
        """
        voices string using nato phonetics.

        Parameters
        ----------
        the_string : str
        String to voicify.
        """
        logger.debug("Voicing: %s", self.say)
        if sd is None:
            logger.warning("Sounddevice/portaudio not installed.")
            return

        # TODO check to make sure the sound device setting is valid. if not, default to
        # first in list. If user is on a laptop it is likely that sound devices change
        device_name = fsutils.read_settings().get("sounddevice", "default")

        sd.default.device = device_name
        sd.default.samplerate = 44100.0

        op_path = fsutils.USER_DATA_PATH / 'operator' / self.operator
        if "[" in self.say:
            sub_string = self.say.strip("[]").lower()
            filename = f"{str(op_path)}/{sub_string}.wav"
            if Path(filename).is_file():
                logger.debug("Voicing: %s", filename)
                try:
                    data, _fs = soundfile.read(filename, dtype="float32")
                    self.radio.set_ptt(True)
                    sd.play(data, blocking=False)
                    # _status = sd.wait()
                    self.radio.set_ptt(False)
                except Exception as err:
                    self.radio.set_ptt(False)
                    self.show_message_box(f"Couldn't play audio {filename}: {err}")
                    logger.exception("Could play audio")

            return
        self.radio.set_ptt(True)
        for letter in self.say.lower():
            if self.stop:
                break
            if letter in "abcdefghijklmnopqrstuvwxyz 1234567890/":
                if letter == " ":
                    letter = "space"
                if letter == '/':
                    letter = "stroke"

                filename = f"{str(op_path)}/{letter}.wav"
                if Path(filename).is_file():
                    logger.debug("Voicing: %s", filename)
                    try:
                        data, _fs = soundfile.read(filename, dtype="float32")
                        sd.play(data, blocking=False)
                        logger.debug("%s", f"{sd.wait()}")
                    except Exception as err:
                        self.radio.set_ptt(False)
                        self.show_message_box(f"Couldn't play audio {filename}: {err}")
                        logger.exception("Could play audio")
                        break
        self.radio.set_ptt(False)

    def show_message_box(self, message: str) -> None:
        message_box = QtWidgets.QMessageBox()
        message_box.setIcon(QtWidgets.QMessageBox.Icon.Information)
        message_box.setText(message)
        message_box.setWindowTitle("Information")
        message_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        _ = message_box.exec()
