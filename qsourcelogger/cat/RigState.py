from dataclasses import dataclass
from typing import Optional


@dataclass
class RigState:
    id: Optional[str] = None
    vfotx_hz: Optional[int] = None
    vforx_hz: Optional[int] = None
    bandwidth_hz: Optional[int] = None
    mode: Optional[str] = None
    power: Optional[int] = None
    error: Optional[str] = None
    is_split: Optional[bool] = False
    is_ptt: Optional[bool] = False
