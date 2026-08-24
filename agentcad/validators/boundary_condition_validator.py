class BoundaryConditionValidator:
    def validate(self, boundary_conditions, region_names):
        return [bc.id for bc in boundary_conditions if bc.target_region not in region_names]
