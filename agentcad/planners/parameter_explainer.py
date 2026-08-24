from __future__ import annotations


class ParameterExplainer:
    _EXPLANATIONS = {
        "young_modulus": "Young's modulus controls elastic stiffness; larger values reduce elastic deformation for the same load and geometry.",
        "poisson_ratio": "Poisson's ratio controls lateral contraction/expansion under axial strain and affects the 3D elastic constitutive response.",
        "density": "Density is required for body-force loads such as gravity and for inertia-based analyses.",
        "global_element_size": "The global element size controls mesh resolution: smaller elements usually improve spatial resolution but increase cost.",
    }

    def explain(self, path: str) -> str | None:
        key = path.split(".")[-1]
        return self._EXPLANATIONS.get(key)
