from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

from qsourcelogger import fsutils

_cache = {}

def get_pixmap(dxcc: int, height: int = None):
    cached = _cache.get((dxcc, height), None)
    if cached:
        return cached
    if height:
        cached = _cache.get((dxcc, None), None)
    if not cached:
        cached = QPixmap(str(fsutils.APP_DATA_PATH / "flags" / f"{dxcc}.png"))
        _cache[(dxcc, None)] = cached
    if not height:
        return cached
    cached = cached.scaledToHeight(height, Qt.TransformationMode.SmoothTransformation)
    _cache[(dxcc, height)] = cached
    return cached
