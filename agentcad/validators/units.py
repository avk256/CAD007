from __future__ import annotations

from agentcad.models.common import QuantityParameter


_LENGTH_TO_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0}
_FORCE_TO_N = {"n": 1.0, "kn": 1000.0}
_STRESS_TO_MPA = {"pa": 1e-6, "kpa": 1e-3, "mpa": 1.0, "gpa": 1000.0, "n/mm²": 1.0, "n/mm2": 1.0}
_DENSITY_TO_TONNE_MM3 = {"kg/m³": 1e-12, "kg/m3": 1e-12, "g/cm³": 1e-9, "g/cm3": 1e-9}
_ACCEL_TO_MM_S2 = {"m/s²": 1000.0, "m/s2": 1000.0, "mm/s²": 1.0, "mm/s2": 1.0}


def _norm(unit: str | None) -> str:
    return (unit or "").strip().lower()


def convert_length_to_mm(q: QuantityParameter) -> float:
    return _convert(q, _LENGTH_TO_MM, "length")


def convert_force_to_n(q: QuantityParameter) -> float:
    return _convert(q, _FORCE_TO_N, "force")


def convert_stress_to_mpa(q: QuantityParameter) -> float:
    return _convert(q, _STRESS_TO_MPA, "stress/pressure")


def convert_density_to_tonne_mm3(q: QuantityParameter) -> float:
    return _convert(q, _DENSITY_TO_TONNE_MM3, "density")


def convert_acceleration_to_mm_s2(q: QuantityParameter) -> float:
    return _convert(q, _ACCEL_TO_MM_S2, "acceleration")


def _convert(q: QuantityParameter, table: dict[str, float], dimension: str) -> float:
    if q.value is None:
        raise ValueError(f"{q.name} has no value")
    unit = _norm(q.unit)
    if unit not in table:
        raise ValueError(f"Unsupported {dimension} unit '{q.unit}' for {q.name}")
    return float(q.value) * table[unit]
