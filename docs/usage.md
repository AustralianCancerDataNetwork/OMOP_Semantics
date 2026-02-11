# e2e Use of OMOP Semantic Registry in ETL

## What are we doing?

Defining in a structured way what conventions look like so that it is machine ingestable and therefore testable and can be added into ETL pipeline hooks.

*Load registry & profiles*

```python

from pathlib import Path
from omop_semantics.runtime import OmopSemanticEngine

instance_base = Path('schema/instances')
profile_base = Path('schema/configuration/profiles')


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