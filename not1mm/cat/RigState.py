from dataclasses import dataclass
from typing import Optional


@dataclass
class RigState:
    vfoa_hz: Optional[int] = None
    vfob_hz: Optional[int] = None
    bandwidth_hz: Optional[int] = None
    mode: Optional[str] = None
    power: Optional[int] = None
    error: Optional[str] = None
    is_vfob_active: Optional[bool] = False
    is_split: Optional[bool] = False
    is_ppt: Optional[bool] = False
