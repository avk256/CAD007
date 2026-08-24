from agentcad.models.mesh import ElementFamily, ModelDimension, ModelIdealization
class MeshValidator:
    def validate(self, mesh):
        issues=[]
        if mesh.idealization == ModelIdealization.SOLID_3D and mesh.dimension != ModelDimension.D3: issues.append("solid_3d requires 3D mesh")
        if mesh.idealization == ModelIdealization.SOLID_3D and mesh.element_family != ElementFamily.TETRAHEDRON: issues.append("v3.0 supports tetrahedron for solid_3d")
        return issues
