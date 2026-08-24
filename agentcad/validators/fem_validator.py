class FEMValidator:
    def validate(self, structural):
        return [] if structural.enabled else ["Structural analysis is disabled."]
