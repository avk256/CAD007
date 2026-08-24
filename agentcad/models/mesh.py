from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from .common import QuantityParameter


class ModelDimension(str, Enum):
    D1 = "1D"
    D2 = "2D"
    D3 = "3D"


class ModelIdealization(str, Enum):
    BEAM_1D = "beam_1d"
    SHELL_2D = "shell_2d"
    SOLID_3D = "solid_3d"


class ElementFamily(str, Enum):
    TRUSS = "truss"
    BEAM = "beam"
    TRIANGLE = "triangle"
    QUADRILATERAL = "quadrilateral"
    TETRAHEDRON = "tetrahedron"
    HEXAHEDRON = "hexahedron"


class ElementOrder(str, Enum):
    FIRST = "first"
    SECOND = "second"


class MeshSizeMode(str, Enum):
    EXPLICIT = "explicit"
    AUTO = "auto"
    UNSET = "unset"


class LocalRefinement(BaseModel):
    target_region: str
    element_size: QuantityParameter


class MeshSpec(BaseModel):
    dimension: Optional[ModelDimension] = None
    idealization: Optional[ModelIdealization] = None
    element_family: Optional[ElementFamily] = None
    element_order: Optional[ElementOrder] = None
    global_size_mode: MeshSizeMode = MeshSizeMode.UNSET
    global_element_size: QuantityParameter = Field(default_factory=lambda: QuantityParameter(name="global_element_size", unit="mm", required=False))
    local_refinements: list[LocalRefinement] = Field(default_factory=list)
    shell_thickness: Optional[QuantityParameter] = None
    beam_section_description: Optional[str] = None
