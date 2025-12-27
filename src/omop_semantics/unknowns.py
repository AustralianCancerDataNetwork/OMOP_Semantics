from .base import ConceptEnum

class Unknown(ConceptEnum):
    generic = 4129922
    gender = 4214687
    condition = 44790729
    cancer = 36402660
    grade = 4264626
    stage = 36768646
    stage_edition = 1634449
    cob = 40482029
    drug_trial = 4090378
    therapeutic_regimen = 4207655

    @classmethod
    def is_unknown(cls, concept_id: int | None) -> bool:
        return concept_id is None or concept_id in cls.values()