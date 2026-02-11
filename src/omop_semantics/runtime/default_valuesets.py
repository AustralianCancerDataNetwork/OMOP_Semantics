from pathlib import Path
from linkml_runtime.loaders import yaml_loader
from omop_semantics.runtime.utils import load_pydantic_class
from omop_semantics.schema.generated_models.omop_named_sets import CDMValueSets, OmopEnum, CDMSemanticUnits
from omop_semantics.runtime.value_sets import compile_valuesets, index_semantic_units, interpolate_valuesets, RuntimeValueSets
from omop_semantics import SCHEMA_DIR, INSTANCE_DIR

schema_path = SCHEMA_DIR / 'core' / 'omop_named_sets.yaml'
enumerator_instances = INSTANCE_DIR / "enumerators.yaml"
valueset_definitions = INSTANCE_DIR / "valuesets.yaml"

enumerators = yaml_loader.load(
    f'{INSTANCE_DIR / "enumerators.yaml"}',
    target_class=CDMSemanticUnits,
)

idx = index_semantic_units(enumerators)
value_sets = yaml_loader.load_as_dict(str(INSTANCE_DIR / 'valuesets.yaml'))
value_set_objects = interpolate_valuesets(value_sets, idx)
runtime = compile_valuesets(value_set_objects)

