from pathlib import Path
from typing import Iterable, Sequence
from linkml_runtime.loaders import yaml_loader
from omop_semantics.schema.generated_models.omop_semantic_registry import (
    RegistryFragment, 
    RegistryGroup,
    OmopCdmProfile,
    CDMProfiles
)


from collections import defaultdict
from pathlib import Path
from typing import TypeVar, Type, cast, Iterable

T = TypeVar("T")

def load_linkml(path: Path, cls: Type[T]) -> T:
    return cast(T, yaml_loader.load(str(path), target_class=cls))

def load_profiles(path: Path) -> dict[str, OmopCdmProfile]:
    raw = load_linkml(path, CDMProfiles)

    if raw.profiles is None:
        raise TypeError(f"Expected CDMProfiles from {path}, got {type(raw)}")
    
    return {p.name: p for p in raw.profiles}

def load_registry_fragment(path: Path) -> RegistryFragment:
    raw = load_linkml(path, RegistryFragment)
    return raw

def interpolate_profiles(group: dict, profiles: dict[str, OmopCdmProfile]) -> None:
    for member in group.get("registry_members", []) or []:
        profile_name = member.get("cdm_profile")
        if not profile_name:
            raise ValueError(f"Missing cdm_profile in member {member.get('name')}")

        profile = profiles.get(profile_name)
        if not profile:
            raise KeyError(f"Unknown cdm_profile '{profile_name}'")

        member["cdm_profile"] = {
            "name": profile.name,
            "cdm_table": profile.cdm_table,
            "concept_slot": profile.concept_slot,
            "value_slot": profile.value_slot,
        }

        member.pop("concept_slot", None)
        member.pop("value_slot", None)


def merge_instance_files(
    paths: Iterable[Path],
    profiles: dict[str, OmopCdmProfile],
) -> dict:
    merged_groups: list[dict] = []
    seen_groups: set[str] = set()

    for p in paths:
        data = yaml_loader.load_as_dict(str(p))
        if not isinstance(data, dict):
            raise TypeError(f"Expected mapping at top level in {p}, got {type(data)}")

        for group in data.get("groups", []) or []:
            name = group.get("name")
            if not name:
                raise ValueError(f"Unnamed group in {p}: {group}")

            if name in seen_groups:
                raise ValueError(f"Duplicate RegistryGroup '{name}' in {p}")

            interpolate_profiles(group, profiles)

            merged_groups.append(group)
            seen_groups.add(name)

    return {
        "groups": merged_groups
    }

def merge_registry_fragments(fragments: Sequence[RegistryFragment]) -> RegistryFragment:
    groups: list[RegistryGroup] = []

    for frag in fragments:
        if frag.groups:
            groups.extend(frag.groups)

    return RegistryFragment(groups=groups)




# def load_profile_objects(path: Path) -> dict[str, dict]:
#     raw = yaml_loader.load_as_dict(str(path))

#     if not isinstance(raw, dict):
#         raise TypeError(f"Expected mapping at top level in {path}, got {type(raw)}")

#     profiles = raw.get("profiles")
#     if not isinstance(profiles, list):
#         raise TypeError(f"Expected 'profiles' list in {path}, got {type(profiles)}")
    
#     out: dict[str, dict] = {}

#     for obj in profiles:
#         if not isinstance(obj, dict):
#             continue

#         name = obj.get("name")
#         if not isinstance(name, str):
#             raise ValueError(f"Profile missing valid 'name' in {path}: {obj}")

#         out[name] = obj

#     return out