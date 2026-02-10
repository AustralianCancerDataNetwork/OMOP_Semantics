from pathlib import Path
from linkml_runtime import SchemaView
from linkml.utils.datautils import infer_root_class
import importlib.util, json, subprocess
from ruamel.yaml.scalarstring import LiteralScalarString

BASE_DIR = Path(__file__).resolve().parent.parent
GENERATED_MODELS_DIR = BASE_DIR / "schema" / "generated_models"

def generate_pydantic_from_linkml(schema_path: Path):
    """
    Generate a single Pydantic model from a LinkML schema using the linkml-gen-pydantic command.
    """
    GENERATED_MODELS_DIR.mkdir(exist_ok=True)
    module_name = schema_path.stem

    # linkml command
    cmd = [
        "uv",
        "run",
        "gen-pydantic",
        str(schema_path)
    ]

    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if proc.returncode != 0:
        raise RuntimeError(
            f"gen-pydantic failed for {schema_path}\n\n"
            f"STDOUT:\n{proc.stdout}\n\n"
            f"STDERR:\n{proc.stderr}"
        )
    
    output_file = GENERATED_MODELS_DIR / f"{module_name}.py"
    output_file.write_text(proc.stdout)


def load_pydantic_class(
        model_name: str, 
        linkml_schema: str | Path, 
        module_path: Path | None = None, 
        overwrite: bool = False,
        prefer_root: bool = True
    ) -> type:
    """
    Load a generated Pydantic class corresponding to the LinkML tree root.

    Steps:
    1. Load the LinkML schema (YAML).
    2. Infer the root class using LinkML's official mechanism.
    3. Load that class from the generated Pydantic module.
    4. Fall back to filename→CamelCase if needed.
    """
    schema_path: Path
    if type(linkml_schema) == Path:
        schema_path = linkml_schema
    else:
        schema_path = Path(linkml_schema)
    
    if not schema_path.exists():
        raise FileNotFoundError(
            f"Schema not found: {schema_path}. Expected LinkML schema for '{model_name}'."
        )

    sv = SchemaView(schema_path)
    root_class_name = infer_root_class(sv)

    if not root_class_name:
        raise RuntimeError(
            f"Could not infer a root class for schema: {schema_path}. "
            "Ensure that at least one class has `tree_root: true` or is inferable."
        )
    if not module_path:
        module_path = GENERATED_MODELS_DIR / f"{schema_path.stem}.py"
    if not module_path.exists() or overwrite:
        generate_pydantic_from_linkml(schema_path)

    spec = importlib.util.spec_from_file_location(model_name, module_path)
    module = importlib.util.module_from_spec(spec) # type: ignore
    spec.loader.exec_module(module) # type: ignore

    # Try to load the inferred class
    if prefer_root and root_class_name and hasattr(module, root_class_name):
        return getattr(module, root_class_name)


    if hasattr(module, model_name):
        return getattr(module, model_name)

    # if we cannot find an inferred tree_root, assume class has same name as file but in CamelCase
    fallback_class = "".join(p.capitalize() for p in model_name.split("_"))
    if hasattr(module, fallback_class):
        return getattr(module, fallback_class)

    available = [k for k, v in module.__dict__.items() if isinstance(v, type)]
    raise AttributeError(
        f"Could not locate the inferred root class '{root_class_name}' "
        f"in generated module {module_path}.\n"
        f"Available classes: {available}"
    )