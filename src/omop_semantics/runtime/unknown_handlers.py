from dataclasses import dataclass
from typing import Literal

"""
This module defines a standard way to represent unknown values in the OMOP CDM.
The idea is to have a consistent set of "unknown" concepts that can be used and 
interpreted across different domains and contexts to indicate that a value is 
missing, not recorded, not applicable, etc.

TODO: move this to linkml specification and generate from there, 
or at least make it more generic and less tied to CDM concepts
"""

UnknownReason = Literal[
    "missing",
    "not_recorded",
    "not_applicable",
    "ambiguous",
    "mapping_failed",
    "default_value"
]

@dataclass(frozen=True)
class UnknownValue:
    concept_id: int
    label: str
    reason: UnknownReason | None = None

UNKNOWN = {
    "generic": UnknownValue(4129922, "Unknown", "missing"),
    "gender": UnknownValue(4214687, "Gender Unknown", "missing"),
    "condition": UnknownValue(44790729, "Unknown problem", "mapping_failed"),
    "cancer": UnknownValue(36402660, "Unknown histology of unknown primary site", "mapping_failed"),
    "grade": UnknownValue(4264626, "Grade not determined", "not_recorded"),
    "stage": UnknownValue(36768646, "Cancer Modifier Origin Grade X", "not_recorded"),
    "cob": UnknownValue(40482029, "Country of birth unknown", "missing"),
    "stage_edition": UnknownValue(1634449, "8th", "default_value"),
    "therapeutic_regimen": UnknownValue(4207655, "prescription of therapeutic regimen", "mapping_failed"),
    "drug_trial": UnknownValue(4207655, "clinical drug trial", "ambiguous"),
}
