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


linkml_meta = LinkMLMeta({'default_prefix': 'omop',
     'default_range': 'string',
     'description': 'A set of OMOP semantic templates describing how one or more '
                    'OMOP concepts are represented in OMOP CDM tables (e.g. '
                    'observation, measurement).\n',
     'id': 'https://example.org/omop_semantics',
     'imports': ['linkml:types', '../core/omop_base', '../core/omop_templates'],
     'name': 'template_set',
     'prefixes': {'linkml': {'prefix_prefix': 'linkml',
                             'prefix_reference': 'https://w3id.org/linkml/'},
                  'omop': {'prefix_prefix': 'omop',
                           'prefix_reference': 'https://athena.ohdsi.org/search-terms/terms/'}},
     'source_file': '../omop_semantics/schema/configuration/registry/template_set.yaml',
     'title': 'OMOP Semantic Templates'} )

class CdmTable(str, Enum):
    """
    OMOP CDM table to which a semantic template applies
    """
    observation = "observation"
    measurement = "measurement"
    drug_exposure = "drug_exposure"
    procedure_occurrence = "procedure_occurrence"
    condition_occurrence = "condition_occurrence"



class OmopSemanticObject(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'abstract': True, 'from_schema': 'https://example.org/omop_semantics'})

    class_uri: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject']} })
    name: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject', 'OmopTemplate']} })
    notes: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject', 'OmopTemplate']} })


class OmopGroup(OmopSemanticObject):
    """
    Named group of OMOP concepts defined by their membership in a particular group, such  as hierarchy and / or domain. Importantly, this is not a static definition and if the vocabularies are updated, the membership of these groups may change. This is intended to be used for defining sets of concepts that are used in semantic definitions, such as the set of all  T stage concepts.

    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/omop_semantics',
         'slot_usage': {'class_uri': {'equals_string': 'OmopGroup',
                                      'name': 'class_uri'}}})

    parent_concepts: Optional[list[Concept]] = Field(default=[], description="""Semantic parent concepts or grouping parents.""", json_schema_extra = { "linkml_meta": {'domain_of': ['OmopGroup']} })
    class_uri: Literal["OmopGroup"] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject'], 'equals_string': 'OmopGroup'} })
    name: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject', 'OmopTemplate']} })
    notes: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject', 'OmopTemplate']} })


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
    name: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject', 'OmopTemplate']} })
    notes: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject', 'OmopTemplate']} })


class OmopEnum(OmopSemanticObject):
    """
    Enumeration of permissible values for a particular slot. This is intended to be used for defining slots that have a fixed set of permissible values, such as the staging axis (T, N, M, Group). This will not update dynamically with vocabulary updates, so should be used for concepts that are  short lists and not expected to change over time.

    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/omop_semantics',
         'slot_usage': {'class_uri': {'equals_string': 'OmopEnum',
                                      'name': 'class_uri'}}})

    enum_members: list[Concept] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopEnum']} })
    class_uri: Literal["OmopEnum"] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject'], 'equals_string': 'OmopEnum'} })
    name: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject', 'OmopTemplate']} })
    notes: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject', 'OmopTemplate']} })


class Concept(ConfiguredBaseModel):
    """
    Concept that serves as a member of an OmopEnum. This is intended to be used for defining the permissible values of an OmopEnum, which is a fixed enumeration  of concepts that does not change dynamically with vocabulary updates.  The concept_id and label slots are used to specify the concept_id  and label of the concept that serves as a member of the enumeration.

    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/omop_semantics'})

    concept_id: Optional[int] = Field(default=None, description="""OMOP concept_id""", json_schema_extra = { "linkml_meta": {'domain_of': ['OmopConcept', 'Concept']} })
    label: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopConcept', 'Concept']} })


class OmopTemplate(ConfiguredBaseModel):
    """
    A compositional semantic template describing how one or more OMOP concepts are represented in OMOP CDM tables (e.g. observation, measurement).

    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/omop_semantics'})

    name: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject', 'OmopTemplate']} })
    role: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopTemplate']} })
    entity_concept: Optional[Union[OmopConcept, OmopEnum, OmopGroup]] = Field(default=None, description="""Concept or group of concepts that may populate the CDM concept slot for this template. If a group or enumeration is provided, any member  of the group or enumeration is valid.
""", json_schema_extra = { "linkml_meta": {'any_of': [{'range': 'OmopGroup'},
                    {'range': 'OmopEnum'},
                    {'range': 'OmopConcept'}],
         'domain_of': ['OmopTemplate']} })
    value_concept: Optional[Union[OmopConcept, OmopEnum, OmopGroup]] = Field(default=None, description="""Group of permissible values for value slots (e.g. value_as_concept_id).
""", json_schema_extra = { "linkml_meta": {'any_of': [{'range': 'OmopGroup'},
                    {'range': 'OmopEnum'},
                    {'range': 'OmopConcept'}],
         'domain_of': ['OmopTemplate']} })
    cdm_table: CdmTable = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopTemplate']} })
    concept_slot: str = Field(default=..., description="""The slot in the CDM table that holds the concept_id for this template
""", json_schema_extra = { "linkml_meta": {'domain_of': ['OmopTemplate']} })
    value_slot: Optional[str] = Field(default=None, description="""The slot in the CDM table that holds the value for this template
""", json_schema_extra = { "linkml_meta": {'domain_of': ['OmopTemplate']} })
    notes: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject', 'OmopTemplate']} })


class TemplateSet(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/omop_semantics', 'tree_root': True})

    templates: Optional[list[OmopTemplate]] = Field(default=[], json_schema_extra = { "linkml_meta": {'domain_of': ['TemplateSet']} })


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
OmopSemanticObject.model_rebuild()
OmopGroup.model_rebuild()
OmopConcept.model_rebuild()
OmopEnum.model_rebuild()
Concept.model_rebuild()
OmopTemplate.model_rebuild()
TemplateSet.model_rebuild()
