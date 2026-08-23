from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UnitDefinition:
    dimension: str
    to_canonical: float


# Canonical engineering units used for validation:
# length mm, force N, stress MPa, density kg/m3, acceleration mm/s2, moment N*mm.
UNITS: dict[str, UnitDefinition] = {
    "1": UnitDefinition("dimensionless", 1.0),
    "": UnitDefinition("dimensionless", 1.0),
    "mm": UnitDefinition("length", 1.0),
    "cm": UnitDefinition("length", 10.0),
    "m": UnitDefinition("length", 1000.0),
    "N": UnitDefinition("force", 1.0),
    "kN": UnitDefinition("force", 1000.0),
    "Pa": UnitDefinition("stress", 1e-6),
    "kPa": UnitDefinition("stress", 1e-3),
    "MPa": UnitDefinition("stress", 1.0),
    "GPa": UnitDefinition("stress", 1000.0),
    "N/mm^2": UnitDefinition("stress", 1.0),
    "N/mm²": UnitDefinition("stress", 1.0),
    "kg/m^3": UnitDefinition("density", 1.0),
    "kg/m³": UnitDefinition("density", 1.0),
    "g/cm^3": UnitDefinition("density", 1000.0),
    "g/cm³": UnitDefinition("density", 1000.0),
    "m/s^2": UnitDefinition("acceleration", 1000.0),
    "m/s²": UnitDefinition("acceleration", 1000.0),
    "mm/s^2": UnitDefinition("acceleration", 1.0),
    "mm/s²": UnitDefinition("acceleration", 1.0),
    "N*mm": UnitDefinition("moment", 1.0),
    "N·mm": UnitDefinition("moment", 1.0),
    "N*m": UnitDefinition("moment", 1000.0),
    "N·m": UnitDefinition("moment", 1000.0),
    "kN*m": UnitDefinition("moment", 1_000_000.0),
    "kN·m": UnitDefinition("moment", 1_000_000.0),
}


def normalize_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    return unit.strip()


def convert_to_canonical(value: float, unit: str, expected_dimension: str) -> float:
    unit = normalize_unit(unit) or ""
    definition = UNITS.get(unit)
    if definition is None:
        raise ValueError(f"Unsupported unit: {unit}")
    if definition.dimension != expected_dimension:
        raise ValueError(
            f"Unit {unit!r} has dimension {definition.dimension}, expected {expected_dimension}."
        )
    return value * definition.to_canonical
