# e2e Use of OMOP Semantic Registry in ETL

## What are we doing?

Defining in a structured way what conventions look like so that it is machine ingestable and therefore testable and can be added into ETL pipeline hooks.

*Load registry & profiles*

```python

from pathlib import Path
from omop_semantics.runtime import OmopSemanticEngine, RegistryFragment
from omop_semantics.runtime.instance_loader import load_registry_fragment, load_profiles, load_symbol_module
from linkml_runtime.loaders import yaml_loader
from omop_semantics import SCHEMA_DIR, INSTANCE_DIR


instance_base = INSTANCE_DIR
profile_base = SCHEMA_DIR / "profiles"

engine = OmopSemanticEngine.from_yaml_paths(
    registry_paths=[
        instance_base / "demography.yaml",
        instance_base / "registry/staging.yaml",
    ],
    profile_paths=[
        profile_base / "omop_profiles.yaml",
    ],
)

```

*Example: Design-time*

This specifies that if you are looking for a valid location for country of birth, you need to use the observation_simple template and select for child concepts of `4155450`

```yaml
      name: Country of birth
      role: demographic
      entity_concept:
        name: Country of Birth
        class_uri: OmopGroup
        parent_concepts:
        - concept_id: 4155450
          label: Country of birth
      cdm_profile: observation_simple
```

Cross-referencing against the available profiles, we see that the `observation_simple` template does not use the `value_as` fields, populating instead the `observation_concept_id` field directlly.

```yaml
profiles:
  - name: observation_simple
    cdm_table: observation
    concept_slot: observation_concept_id
```

*Example: Run-time resolution*

Note that we do not want to be either

1. redefining full classes for simple data structures that conform exactly to the defined profiles, or
2. having to repeat full profiles in registry fragments. 

Instead, we have a pre-processing step that merges instance files with profiles to create a "registry fragment" that can be used to initialise the resolver

```python

profiles = load_profiles(instance_base / "profiles.yaml")

registry_dict = merge_instance_files(
    paths = [instance_base / "demographic.yaml"],
    profiles = profiles
)

```
On initial load, we just get a reference to the template as a string, which does not conform to the template structure in its own right...

```python

yaml_loader.load_as_dict(f'{instance_base / "demographic.yaml"}')['groups'][0]['registry_members'][0]

# {'name': 'Country of birth',
#  'role': 'demographic',
#  'entity_concept': {'name': 'Country of Birth',
#   'class_uri': 'OmopGroup',
#   'parent_concepts': [{'concept_id': 4155450, 'label': 'Country of birth'}]},
#  'cdm_profile': 'observation_simple'}

```

after we apply the profiles, we get a fully conformed registry fragment with all the relevant information from the profile

```python

profiles['observation_simple']

# OmopCdmProfile(name='observation_simple', cdm_table='observation', concept_slot='observation_concept_id', value_slot=None)

```

this structure can now be used to properly instantiate the template classes and then fully used for rendering, validation, etc. downstream

```python

registry_dict['groups'][0]['registry_members'][0]

{'name': 'Country of birth',
 'role': 'demographic',
 'entity_concept': {'name': 'Country of Birth',
  'class_uri': 'OmopGroup',
  'parent_concepts': [{'concept_id': 4155450, 'label': 'Country of birth'}]},
 'cdm_profile': {'name': 'observation_simple',
  'cdm_table': 'observation',
  'concept_slot': 'observation_concept_id',
  'value_slot': None}}

```

other more complex modules can be created as full linkml subschemas and then loaded directly instead

```python

staging_symbols = load_symbol_module(profile_base / 'omop_staging.yaml')
modifier_symbols = load_symbol_module(profile_base / 'omop_modifiers.yaml')

staging_symbols['TStageConcepts']

# {'is_a': 'RegistryGroup',
#  'name': 'TStageConcepts',
#  'role': 'staging',
#  'registry_members': ['T0', 'T1', 'T2', 'T3', 'T4', 'Ta', 'Tis', 'TX']}

staging_symbols['T0']

# {'class_uri': 'OmopGroup',
#  'parent_concepts': [{'concept_id': 1634213, 'label': 'T0'}],
#  'role': 'staging'}

registry_fragment = yaml_loader.load(
    registry_dict,
    target_class=RegistryFragment
)

engine = OmopSemanticEngine(
    registry_fragment=registry_fragment,
    profile_objects=[staging_symbols, modifier_symbols]   # or merge with profile symbols too
)

```

Now that our engine is fully instantiated...

```python
tpl = engine.registry_runtime.get_runtime("Country of birth")
tpl.entity_concept_ids
# {4155450}
```

*Example: ETL-time compiled templates*

Example ETL routing logic:

```python

def emit_row_from_template(
    tpl: RuntimeTemplate,
    *,
    concept_id: int,
    value: str | int | None,
    person_id: int,
    date: str,
) -> tuple[str, dict]:
    """
    Emit an OMOP CDM row driven entirely by the template's CDM profile.

    Returns (cdm_table_name, row_dict)
    """
    profile = tpl.cdm_profile

    row: dict[str, object] = {
        profile.concept_slot: concept_id,
        "person_id": person_id,
        "observation_date": date,   # date handling could also be driven by profile later if needed
    }

    if profile.value_slot:
        row[profile.value_slot] = value

    return profile.cdm_table, row


tpl = engine.registry_runtime.get_runtime("Postcode")

# tpl.cdm_profile.name == "observation_string"

table, row = emit_row_from_template(
    tpl,
    concept_id=4083591,  # Postcode concept
    value="2031",
    person_id=123,
    date="2024-01-01",
)

table
# "observation"

row
# {
#   "observation_concept_id": 4083591,
#   "value_as_string": "2031",
#   "person_id": 123,
#   "observation_date": "2024-01-01"
# }

tpl = engine.registry_runtime.get_runtime("Language spoken")
# profile: observation_coded


table, row = emit_row_from_template(
    tpl,
    concept_id=4052785,     # "Language spoken"
    value=4182347,         # "English"
    person_id=123,
    date="2024-01-01",
)

row
# {
#   "observation_concept_id": 4052785,
#   "value_as_concept_id": 4182347,
#   "person_id": 123,
#   "observation_date": "2024-01-01"
# }


```