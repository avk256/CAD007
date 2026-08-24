class MaterialValidator:
    def validate(self, material):
        issues = []
        if material.young_modulus.value is None or material.young_modulus.value <= 0:
            issues.append("Young modulus must be positive and defined.")
        if material.poisson_ratio.value is None or not (-1 < material.poisson_ratio.value < 0.5):
            issues.append("Poisson ratio must satisfy -1 < nu < 0.5.")
        return issues
