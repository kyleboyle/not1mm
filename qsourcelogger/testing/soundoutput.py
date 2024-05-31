
import sounddevice as sd
import soundfile

if __name__ == '__main__':
    sd.default.device = "USB Audio Device, Core Audio"
    #sd.default.device = "VG248"
   # sd.default.device = "MacBook Pro Speakers"
    sd.default.samplerate = 44100.0

    data, _fs = soundfile.read('/Users/kyle/.qsourcelogger/operator/VE9KZ/e.wav', dtype="float32")
    #sd.default
    sd.play(data, blocking=True)