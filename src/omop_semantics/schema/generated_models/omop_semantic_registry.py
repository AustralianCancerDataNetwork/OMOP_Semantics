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
     'description': 'Grouped registry structure for OMOP concept profiles used for '
                    'complex semantic definitions, such as staging of neoplastic  '
                    'disease through condition modifiers and their appropriate '
                    'handling in episodes.\n',
     'id': 'https://example.org/omop_semantic_registry',
     'imports': ['linkml:types', '../core/omop_templates'],
     'name': 'omop_semantic_registry',
     'prefixes': {'linkml': {'prefix_prefix': 'linkml',
                             'prefix_reference': 'https://w3id.org/linkml/'},
                  'omop': {'prefix_prefix': 'omop',
                           'prefix_reference': 'https://athena.ohdsi.org/search-terms/terms/'}},
     'source_file': '../omop_semantics/schema/configuration/registry/omop_semantic_registry.yaml',
     'title': 'OMOP Semantic Concept Registry'} )

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
    name: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject',
                       'OmopCdmProfile',
                       'OmopTemplate',
                       'Registry',
                       'RegistryGroup']} })
    notes: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject', 'OmopTemplate', 'RegistryGroup']} })


class OmopGroup(OmopSemanticObject):
    """
    Named group of OMOP concepts defined by their membership in a particular group, such  as hierarchy and / or domain. Importantly, this is not a static definition and if the vocabularies are updated, the membership of these groups may change. This is intended to be used for defining sets of concepts that are used in semantic definitions, such as the set of all  T stage concepts.

    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/omop_semantics',
         'slot_usage': {'class_uri': {'equals_string': 'OmopGroup',
                                      'name': 'class_uri'}}})

    parent_concepts: Optional[list[Concept]] = Field(default=[], description="""Semantic parent concepts or grouping parents.""", json_schema_extra = { "linkml_meta": {'domain_of': ['OmopGroup']} })
    class_uri: Literal["OmopGroup"] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject'], 'equals_string': 'OmopGroup'} })
    name: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject',
                       'OmopCdmProfile',
                       'OmopTemplate',
                       'Registry',
                       'RegistryGroup']} })
    notes: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject', 'OmopTemplate', 'RegistryGroup']} })


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
    name: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject',
                       'OmopCdmProfile',
                       'OmopTemplate',
                       'Registry',
                       'RegistryGroup']} })
    notes: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject', 'OmopTemplate', 'RegistryGroup']} })


class OmopEnum(OmopSemanticObject):
    """
    Enumeration of permissible values for a particular slot. This is intended to be used for defining slots that have a fixed set of permissible values, such as the staging axis (T, N, M, Group). This will not update dynamically with vocabulary updates, so should be used for concepts that are  short lists and not expected to change over time.

    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/omop_semantics',
         'slot_usage': {'class_uri': {'equals_string': 'OmopEnum',
                                      'name': 'class_uri'}}})

    enum_members: list[Concept] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopEnum']} })
    class_uri: Literal["OmopEnum"] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject'], 'equals_string': 'OmopEnum'} })
    name: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject',
                       'OmopCdmProfile',
                       'OmopTemplate',
                       'Registry',
                       'RegistryGroup']} })
    notes: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject', 'OmopTemplate', 'RegistryGroup']} })


class OmopValueSet(OmopSemanticObject):
    """
    A semantic grouping of permissible values for a template slot. Members may be OmopConcepts, OmopGroups, or OmopEnums. This represents a registry-level value domain, not a direct OMOP structure.

    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/omop_semantics',
         'slot_usage': {'class_uri': {'equals_string': 'OmopValueSet',
                                      'name': 'class_uri'}}})

    members: Optional[list[OmopSemanticObject]] = Field(default=[], json_schema_extra = { "linkml_meta": {'domain_of': ['OmopValueSet']} })
    class_uri: Literal["OmopValueSet"] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject'], 'equals_string': 'OmopValueSet'} })
    name: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject',
                       'OmopCdmProfile',
                       'OmopTemplate',
                       'Registry',
                       'RegistryGroup']} })
    notes: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject', 'OmopTemplate', 'RegistryGroup']} })


class Concept(ConfiguredBaseModel):
    """
    Concept that serves as a member of an OmopEnum. This is intended to be used for defining the permissible values of an OmopEnum, which is a fixed enumeration  of concepts that does not change dynamically with vocabulary updates.  The concept_id and label slots are used to specify the concept_id  and label of the concept that serves as a member of the enumeration.

    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/omop_semantics'})

    concept_id: Optional[int] = Field(default=None, description="""OMOP concept_id""", json_schema_extra = { "linkml_meta": {'domain_of': ['OmopConcept', 'Concept']} })
    label: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopConcept', 'Concept']} })


class CDMProfiles(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/omop_semantics/cdm_profiles',
         'tree_root': True})

    profiles: Optional[list[OmopCdmProfile]] = Field(default=[], json_schema_extra = { "linkml_meta": {'domain_of': ['CDMProfiles']} })


class OmopCdmProfile(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/omop_semantics/cdm_profiles'})

    name: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject',
                       'OmopCdmProfile',
                       'OmopTemplate',
                       'Registry',
                       'RegistryGroup']} })
    cdm_table: CdmTable = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopCdmProfile']} })
    concept_slot: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopCdmProfile']} })
    value_slot: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopCdmProfile']} })


class OmopTemplate(ConfiguredBaseModel):
    """
    A compositional semantic template describing how one or more OMOP concepts are represented in OMOP CDM tables (e.g. observation, measurement).

    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/omop_semantics'})

    name: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject',
                       'OmopCdmProfile',
                       'OmopTemplate',
                       'Registry',
                       'RegistryGroup']} })
    role: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopTemplate', 'RegistryGroup']} })
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
    cdm_profile: OmopCdmProfile = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopTemplate']} })
    notes: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject', 'OmopTemplate', 'RegistryGroup']} })


class Registry(ConfiguredBaseModel):
    """
    A registry of OMOP concepts, templates, and groups used for complex semantic definitions.

    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/omop_semantic_registry'})

    name: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject',
                       'OmopCdmProfile',
                       'OmopTemplate',
                       'Registry',
                       'RegistryGroup']} })
    description: Optional[str] = Field(default=None, description="""Description of the registry or group, intended for documentation purposes.
""", json_schema_extra = { "linkml_meta": {'domain_of': ['Registry']} })
    fragments: Optional[list[RegistryFragment]] = Field(default=[], description="""List of registry fragments contained in this registry. This is intended for modularisation of units of semantic definitions, such as all concepts related to staging of neoplastic disease so that then can be reused in different registry profile definitions.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Registry']} })


class RegistryFragment(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/omop_semantic_registry', 'tree_root': True})

    groups: Optional[list[RegistryGroup]] = Field(default=[], description="""List of registry groups contained in this registry. This is intended for organisation and documentation  purposes, and does not have any semantic meaning beyond indicating that these groups are part of the same  registry.
""", json_schema_extra = { "linkml_meta": {'domain_of': ['RegistryFragment']} })


class RegistryGroup(ConfiguredBaseModel):
    """
    Named grouping of semantic templates or definitions in the registry, used for organisation, documentation, and navigation. Members are registry symbols, not OMOP concept identifiers.

    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/omop_semantic_registry'})

    name: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject',
                       'OmopCdmProfile',
                       'OmopTemplate',
                       'Registry',
                       'RegistryGroup']} })
    role: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['OmopTemplate', 'RegistryGroup']} })
    registry_members: Optional[list[OmopTemplate]] = Field(default=[], description="""List of registry symbols that are members of this group. These are not OMOP concept identifiers,  but rather references to other symbols in the registry, such as templates or groups. This is intended  for organisation and documentation purposes, and does not have any semantic meaning beyond indicating  that these symbols are related in some way.
""", json_schema_extra = { "linkml_meta": {'domain_of': ['RegistryGroup']} })
    notes: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['OmopSemanticObject', 'OmopTemplate', 'RegistryGroup']} })


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
OmopSemanticObject.model_rebuild()
OmopGroup.model_rebuild()
OmopConcept.model_rebuild()
OmopEnum.model_rebuild()
OmopValueSet.model_rebuild()
Concept.model_rebuild()
CDMProfiles.model_rebuild()
OmopCdmProfile.model_rebuild()
OmopTemplate.model_rebuild()
Registry.model_rebuild()
RegistryFragment.model_rebuild()
RegistryGroup.model_rebuild()
