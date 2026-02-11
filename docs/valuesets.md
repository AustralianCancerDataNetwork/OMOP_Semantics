# Value Sets Runtime

## RuntimeValueSets

::: omop_semantics.runtime.value_sets.RuntimeValueSets

## RuntimeValueSet

::: omop_semantics.runtime.value_sets.RuntimeValueSet

## RuntimeSemanticUnit

::: omop_semantics.runtime.value_sets.RuntimeSemanticUnit

## RuntimeEnum

::: omop_semantics.runtime.value_sets.RuntimeEnum

## RuntimeGroup

::: omop_semantics.runtime.value_sets.RuntimeGroup

## compile_valuesets

::: omop_semantics.runtime.value_sets.compile_valuesets

## interpolate_valuesets

::: omop_semantics.runtime.value_sets.interpolate_valuesets

## index_semantic_units

::: omop_semantics.runtime.value_sets.index_semantic_units

## default_valuesets

# Default Value Sets

This module provides a reference implementation for loading and compiling the default OMOP semantic value sets shipped with the library.

It demonstrates the full runtime loading pipeline:

1. Loading semantic unit definitions (enums, groups, concepts) from YAML.
2. Indexing semantic units by name.
3. Loading high-level value set definitions.
4. Interpolating string references into concrete semantic objects.
5. Compiling the result into runtime-friendly accessors.

This file is intended primarily as:
- a working exemplar of the loading pipeline, and  
- a convenient import point for default registry semantics.

---

## Loading Pipeline

The default value sets are constructed using the following steps:

```python
from pathlib import Path
from linkml_runtime.loaders import yaml_loader

from omop_semantics.schema.generated_models.omop_named_sets import CDMSemanticUnits
from omop_semantics.runtime.value_sets import (
    compile_valuesets,
    index_semantic_units,
    interpolate_valuesets,
    RuntimeValueSets,
)
from omop_semantics import SCHEMA_DIR, INSTANCE_DIR

schema_path = SCHEMA_DIR / "core" / "omop_named_sets.yaml"
enumerator_instances = INSTANCE_DIR / "enumerators.yaml"
valueset_definitions = INSTANCE_DIR / "valuesets.yaml"

# Load semantic units (enums, groups, concepts)
enumerators = yaml_loader.load(
    str(enumerator_instances),
    target_class=CDMSemanticUnits,
)

# Build name → semantic object index
idx = index_semantic_units(enumerators)

# Load valueset definitions (string references)
value_sets = yaml_loader.load_as_dict(str(valueset_definitions))

# Interpolate string references into concrete semantic units
value_set_objects = interpolate_valuesets(value_sets, idx)

# Compile to runtime objects
runtime = compile_valuesets(value_set_objects)
```

### Intended Usage

This module is designed to be imported directly by downstream code (etl, interactive analytics, auto-documentation and/or data validation)

```python

from omop_semantics.runtime.default_valuesets import runtime

concept_id = runtime.genomic.genomic_value_group.genomic_positive

```

It can also be used as a template for loading:

* site-specific value sets,
* project-specific semantic registries, or
* dynamically constructed semantic bundles.

### Notes

* This loader pipeline is intentionally explicit and decomposed for clarity.
* The API surface may be wrapped in higher-level convenience functions in future versions.
* The current design prioritises transparency and inspectability over terseness.