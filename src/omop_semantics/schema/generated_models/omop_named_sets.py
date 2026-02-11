from __future__ import annotations

import re
import sys
from datetime import (
    date,
    datetime,
    time
)
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    ClassVar,
    Literal,
    Optional,
    Union
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer
)


metamodel_version = "None"
version = "None"


class ConfiguredBaseModel(BaseModel):
    model_config = ConfigDict(
        serialize_by_alias = True,
        validate_by_name = True,
        validate_assignment = True,
        validate_default = True,
        extra = "forbid",
        arbitrary_types_allowed = True,
        use_enum_values = True,
        strict = False,
    )

    @model_serializer(mode='wrap', when_used='unless-none')
    def treat_empty_lists_as_none(
            self, handler: SerializerFunctionWrapHandler,
            info: SerializationInfo) -> dict[str, Any]:
        if info.exclude_none:
            _instance = self.model_copy()
            for field, field_info in type(_instance).model_fields.items():
                if getattr(_instance, field) == [] and not(
                        field_info.is_required()):
                    setattr(_instance, field, None)
        else:
            _instance = self
        return handler(_instance, info)



class LinkMLMeta(RootModel):
    root: dict[str, Any] = {}
    model_config = ConfigDict(frozen=True)

    def __getattr__(self, key:str):
        return getattr(self.root, key)

    def __getitem__(self, key:str):
        return self.root[key]

    def __setitem__(self, key:str, value):
        self.root[key] = value

    def __contains__(self, key:str) -> bool:
        return key in self.root


linkml_meta = LinkMLMeta({'default_prefix': 'https://example.org/omop_semantics/cdm_value_sets/',
     'id': 'https://example.org/omop_semantics/cdm_value_sets',
     'imports': ['omop_base'],
     'name': 'cdm_value_sets',
     'source_file': '/Users/z3061723/Documents/CODE/OMOP_Semantics/omop-semantics/src/omop_semantics/schema/configuration/core/omop_named_sets.yaml'} )


class OmopSemanticObject(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'abstract': True, 'from_schema': 'https://example.org/omop_semantics'})

    class_uri: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject']} })
    name: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject', 'CDMSemanticUnits']} })
    notes: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject']} })


class OmopGroup(OmopSemanticObject):
    """
    Named group of OMOP concepts defined by their membership in a particular group, such  as hierarchy and / or domain. Importantly, this is not a static definition and if the vocabularies are updated, the membership of these groups may change. This is intended to be used for defining sets of concepts that are used in semantic definitions, such as the set of all  T stage concepts.

    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/omop_semantics',
         'slot_usage': {'class_uri': {'equals_string': 'OmopGroup',
                                      'name': 'class_uri'}}})

    parent_concepts: Optional[list[Concept]] = Field(default=[], description="""Semantic parent concepts or grouping parents.""", json_schema_extra = { "linkml_meta": {'domain_of': ['OmopGroup']} })
    class_uri: Literal["OmopGroup"] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject'], 'equals_string': 'OmopGroup'} })
    name: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject', 'CDMSemanticUnits']} })
    notes: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject']} })


class OmopConcept(OmopSemanticObject):
    """
    A single OMOP concept with semantic annotations
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/omop_semantics',
         'slot_usage': {'class_uri': {'equals_string': 'OmopConcept',
                                      'name': 'class_uri'}}})

    concept_id: Optional[int] = Field(default=None, description="""OMOP concept_id""", json_schema_extra = { "linkml_meta": {'domain_of': ['OmopConcept', 'Concept']} })
    label: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopConcept', 'Concept']} })
    class_uri: Literal["OmopConcept"] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject'], 'equals_string': 'OmopConcept'} })
    name: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject', 'CDMSemanticUnits']} })
    notes: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject']} })


class OmopEnum(OmopSemanticObject):
    """
    Enumeration of permissible values for a particular slot. This is intended to be used for defining slots that have a fixed set of permissible values, such as the staging axis (T, N, M, Group). This will not update dynamically with vocabulary updates, so should be used for concepts that are  short lists and not expected to change over time.

    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/omop_semantics',
         'slot_usage': {'class_uri': {'equals_string': 'OmopEnum',
                                      'name': 'class_uri'}}})

    enum_members: list[Concept] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopEnum']} })
    class_uri: Literal["OmopEnum"] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject'], 'equals_string': 'OmopEnum'} })
    name: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject', 'CDMSemanticUnits']} })
    notes: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject']} })


class OmopValueSet(OmopSemanticObject):
    """
    A semantic grouping of permissible values for a template slot. Members may be OmopConcepts, OmopGroups, or OmopEnums. This represents a registry-level value domain, not a direct OMOP structure.

    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/omop_semantics',
         'slot_usage': {'class_uri': {'equals_string': 'OmopValueSet',
                                      'name': 'class_uri'}}})

    members: list[CDMSemanticUnits] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopValueSet', 'CDMValueSet']} })
    class_uri: Literal["OmopValueSet"] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject'], 'equals_string': 'OmopValueSet'} })
    name: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject', 'CDMSemanticUnits']} })
    notes: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject']} })


class Concept(ConfiguredBaseModel):
    """
    Concept that serves as a member of an OmopEnum. This is intended to be used for defining the permissible values of an OmopEnum, which is a fixed enumeration  of concepts that does not change dynamically with vocabulary updates.  The concept_id and label slots are used to specify the concept_id  and label of the concept that serves as a member of the enumeration.

    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/omop_semantics'})

    concept_id: Optional[int] = Field(default=None, description="""OMOP concept_id""", json_schema_extra = { "linkml_meta": {'domain_of': ['OmopConcept', 'Concept']} })
    label: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopConcept', 'Concept']} })


class CDMValueSets(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/omop_semantics/cdm_value_sets',
         'tree_root': True})

    valuesets: list[CDMValueSet] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['CDMValueSets']} })


class CDMValueSet(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/omop_semantics/cdm_value_sets'})

    valueset_name: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['CDMValueSet']} })
    members: list[CDMSemanticUnits] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopValueSet', 'CDMValueSet']} })


class CDMSemanticUnits(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/omop_semantics/cdm_value_sets'})

    name: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject', 'CDMSemanticUnits']} })
    named_enumerators: Optional[list[OmopEnum]] = Field(default=[], json_schema_extra = { "linkml_meta": {'domain_of': ['CDMSemanticUnits']} })
    named_concepts: Optional[list[OmopConcept]] = Field(default=[], json_schema_extra = { "linkml_meta": {'domain_of': ['CDMSemanticUnits']} })
    named_groups: Optional[list[OmopGroup]] = Field(default=[], json_schema_extra = { "linkml_meta": {'domain_of': ['CDMSemanticUnits']} })


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
OmopSemanticObject.model_rebuild()
OmopGroup.model_rebuild()
OmopConcept.model_rebuild()
OmopEnum.model_rebuild()
OmopValueSet.model_rebuild()
Concept.model_rebuild()
CDMValueSets.model_rebuild()
CDMValueSet.model_rebuild()
CDMSemanticUnits.model_rebuild()
