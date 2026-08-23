from __future__ import annotations

from agentcad.models.common import IssueKind
from agentcad.models.mesh import (
    ElementFamily, MeshSizeMode, ModelDimension, ModelIdealization, MeshSpec,
)
from agentcad.models.validation import ValidationIssue
from .base import ValidatorBase


_ALLOWED = {
    ModelDimension.D1: {ElementFamily.TRUSS, ElementFamily.BEAM},
    ModelDimension.D2: {ElementFamily.TRIANGLE, ElementFamily.QUADRILATERAL},
    ModelDimension.D3: {ElementFamily.TETRAHEDRON, ElementFamily.HEXAHEDRON},
}

_IDEALIZATION_DIM = {
    ModelIdealization.BEAM_1D: ModelDimension.D1,
    ModelIdealization.SHELL_2D: ModelDimension.D2,
    ModelIdealization.SOLID_3D: ModelDimension.D3,
}


class MeshValidator(ValidatorBase):
    module_name = "mesh"

    def validate(self, mesh: MeshSpec, semantic_regions: set[str]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        if mesh.dimension is None:
            issues.append(self.issue(
                "mesh.dimension.missing", "Не задано розмірність скінченних елементів.",
                kind=IssueKind.MISSING, affected=["mesh.dimension"],
                question="Яку модель використати: 1D, 2D чи 3D?", requires_user=True,
            ))
        if mesh.idealization is None:
            issues.append(self.issue(
                "mesh.idealization.missing", "Не задано модельну ідеалізацію.",
                kind=IssueKind.MISSING, affected=["mesh.dimension"],
                question="Підтвердіть модельну ідеалізацію: beam 1D, shell 2D або solid 3D.",
                requires_user=True,
            ))
        if mesh.element_family is None:
            issues.append(self.issue(
                "mesh.family.missing", "Не задано сімейство скінченних елементів.",
                kind=IssueKind.MISSING, affected=["mesh.element_family"],
                question="Яке сімейство елементів використати для вибраної розмірності?",
                requires_user=True,
            ))
        if mesh.element_order is None:
            issues.append(self.issue(
                "mesh.order.missing", "Не задано порядок скінченних елементів.",
                kind=IssueKind.MISSING, affected=["mesh.element_order"],
                question="Використати елементи першого чи другого порядку?",
                requires_user=True,
            ))

        if mesh.dimension and mesh.element_family and mesh.element_family not in _ALLOWED[mesh.dimension]:
            issues.append(self.issue(
                "mesh.family.incompatible",
                f"Елемент {mesh.element_family.value} несумісний з моделлю {mesh.dimension.value}.",
                kind=IssueKind.CONFLICT, affected=["mesh.dimension", "mesh.element_family"],
                question="Уточніть сумісну розмірність та сімейство скінченних елементів.",
                requires_user=True,
            ))

        if mesh.dimension and mesh.idealization and _IDEALIZATION_DIM[mesh.idealization] != mesh.dimension:
            issues.append(self.issue(
                "mesh.idealization.incompatible",
                "Модельна ідеалізація не відповідає розмірності елементів.",
                kind=IssueKind.CONFLICT, affected=["mesh.dimension"],
                question="Уточніть узгоджені модельну ідеалізацію та розмірність елементів.",
                requires_user=True,
            ))

        if mesh.global_size_mode == MeshSizeMode.UNSET:
            issues.append(self.issue(
                "mesh.size.missing", "Не визначено глобальний розмір сітки і не вибрано AUTO.",
                kind=IssueKind.MISSING, affected=["mesh.global_element_size"],
                question="Задайте глобальний розмір елемента або явно оберіть автоматичний підбір розміру.",
                requires_user=True,
            ))
        elif mesh.global_size_mode == MeshSizeMode.EXPLICIT:
            sub, _ = self.validate_quantity(
                mesh.global_element_size, path="mesh.global_element_size",
                dimension="length", positive=True, required=True,
            )
            issues.extend(sub)

        if mesh.idealization == ModelIdealization.SHELL_2D:
            if mesh.shell_thickness is None:
                issues.append(self.issue(
                    "mesh.shell_thickness.missing", "Для 2D shell-моделі не задано товщину.",
                    kind=IssueKind.MISSING, affected=["mesh.shell_thickness"],
                    question="Яку товщину оболонки використати?", requires_user=True,
                ))
            else:
                sub, _ = self.validate_quantity(
                    mesh.shell_thickness, path="mesh.shell_thickness",
                    dimension="length", positive=True, required=True,
                )
                issues.extend(sub)

        if mesh.idealization == ModelIdealization.BEAM_1D and not mesh.beam_section_description:
            issues.append(self.issue(
                "mesh.beam_section.missing", "Для 1D beam/truss-моделі не задано поперечний переріз.",
                kind=IssueKind.MISSING, affected=["mesh.beam_section"],
                question="Уточніть форму, розміри або характеристики поперечного перерізу 1D моделі.",
                requires_user=True,
            ))

        for idx, ref in enumerate(mesh.local_refinements):
            if ref.target_region not in semantic_regions:
                issues.append(self.issue(
                    f"mesh.refinement.{idx}.target",
                    f"Область локального згущення {ref.target_region!r} відсутня у GeometrySpec.",
                    kind=IssueKind.CONFLICT, affected=["mesh.local_refinements", "geometry.semantic_region"],
                    question=f"Уточніть область локального згущення {ref.target_region!r}.",
                    requires_user=True,
                ))
        return issues
