from enum import Enum
from .base import ConceptEnum

class StageType(Enum):
    CLINICAL = "c"
    PATHOLOGICAL = "p"

class StageEdition(ConceptEnum):
    _6th = 1634647
    _7th = 1633496
    _8th = 1634449

class TStageConcepts(ConceptEnum):
    # used to group tnm mappings into their relevant subtypes
    # preferably create a concept that is the parent of all these T concepts, but for now...
    t0 = 1634213
    t1 = 1635564
    t2 = 1635562
    t3 = 1634376
    t4 = 1634654
    ta = 1635114
    tx = 1635682
    tis = 1634530

class NStageConcepts(ConceptEnum):
    # as above for n...
    n0 = 1633440
    n1 = 1634434
    n2 = 1634119
    n3 = 1635320
    n4 = 1635445
    nx = 1633885

class MStageConcepts(ConceptEnum):
    # and m...
    m0 = 1635624
    m1 = 1635142
    mx = 1633547

class GroupStageConcepts(ConceptEnum):
    # there's a pattern here
    stage0 = 1633754
    stageI = 1633306
    stageII = 1634209
    stageIII = 1633650
    stageIV = 1633308

STAGING_GROUPS = {
    "T": TStageConcepts,
    "N": NStageConcepts,
    "M": MStageConcepts,
    "GROUP": GroupStageConcepts,
}

def staging_axis(concept_id: int) -> str | None:
    for name, enum in STAGING_GROUPS.items():
        if enum.has(concept_id):
            return name
    return None

def is_staging_concept(concept_id: int | None) -> bool:
    if concept_id is None:
        return False
    for enum in STAGING_GROUPS.values():
        if enum.has(concept_id):
            return True
    return False