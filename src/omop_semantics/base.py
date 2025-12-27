from enum import Enum

class ConceptEnum(Enum):
    """
    Base class for OMOP concept enums.
    Values MUST be OMOP concept_ids.
    """

    @classmethod
    def values(cls) -> set[int]:
        return {m.value for m in cls}

    @classmethod
    def labels(cls) -> list[str]:
        return [m.name for m in cls]

    @classmethod
    def has(cls, concept_id: int | None) -> bool:
        if concept_id is None:
            return False
        return concept_id in cls.values()

    @classmethod
    def try_name(cls, concept_id: int | None) -> str | None:
        if concept_id is None:
            return None
        try:
            return cls(concept_id).name
        except ValueError:
            return None
