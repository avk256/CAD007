from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel

from .common import QuantityParameter, Vector3


class LoadType(str, Enum):
    FORCE = "force"
    PRESSURE = "pressure"
    MOMENT = "moment"
    GRAVITY = "gravity"


class LoadSpec(BaseModel):
    id: str
    load_type: LoadType
    magnitude: QuantityParameter
    target_region: Optional[str] = None
    direction: Optional[Vector3] = None
    distribution: str = "uniform"
    coordinate_system: str = "global"
    description: str = ""
