class LoadValidator:
    def validate(self, loads, region_names):
        return [load.id for load in loads if load.target_region and load.target_region not in region_names]
