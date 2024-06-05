from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

import yaml.loader
from snowflake.cli.api.cli_global_context import cli_context
from snowflake.cli.api.constants import DEFAULT_SIZE_LIMIT_MB
from snowflake.cli.api.project.schemas.project_definition import ProjectDefinition
from snowflake.cli.api.project.util import (
    append_to_identifier,
    clean_identifier,
    get_env_username,
    to_identifier,
)
from snowflake.cli.api.secure_path import SecurePath
from snowflake.cli.api.utils.definition_rendering import render_definition_template
from snowflake.cli.api.utils.dict_utils import deep_merge_dicts
from yaml import load

DEFAULT_USERNAME = "unknown_user"


@dataclass
class ProjectProperties:
    project_definition: ProjectDefinition
    raw_project_definition: dict


def _get_merged_project_files(paths: List[Path]) -> dict:
    spaths: List[SecurePath] = [SecurePath(p) for p in paths]
    if len(spaths) == 0:
        raise ValueError("Need at least one definition file.")

    with spaths[0].open("r", read_file_limit_mb=DEFAULT_SIZE_LIMIT_MB) as base_yml:
        definition = load(base_yml.read(), Loader=yaml.loader.BaseLoader)

    for override_path in spaths[1:]:
        with override_path.open(
            "r", read_file_limit_mb=DEFAULT_SIZE_LIMIT_MB
        ) as override_yml:
            overrides = load(override_yml.read(), Loader=yaml.loader.BaseLoader)
            deep_merge_dicts(definition, overrides)

    return definition


def load_project(paths: List[Path]) -> ProjectProperties:
    """
    Loads project definition, optionally overriding values. Definition values
    are merged in left-to-right order (increasing precedence).
    """
    merged_files = _get_merged_project_files(paths)
    rendered_definition = render_definition_template(merged_files)
    return ProjectProperties(
        ProjectDefinition(**rendered_definition), rendered_definition
    )


def generate_local_override_yml(
    project: ProjectDefinition,
) -> ProjectDefinition:
    """
    Generates defaults for optional keys in the same YAML structure as the project
    schema. The returned YAML object can be saved directly to a file, if desired.
    A connection is made using global context to resolve current role and warehouse.
    """
    conn = cli_context.connection
    user = clean_identifier(get_env_username() or DEFAULT_USERNAME)
    role = conn.role
    warehouse = conn.warehouse

    local: dict = {}
    if project.native_app:
        name = clean_identifier(project.native_app.name)
        app_identifier = to_identifier(name)
        user_app_identifier = append_to_identifier(app_identifier, f"_{user}")
        package_identifier = append_to_identifier(app_identifier, f"_pkg_{user}")
        local["native_app"] = {
            "application": {
                "name": user_app_identifier,
                "role": role,
                "debug": True,
                "warehouse": warehouse,
            },
            "package": {"name": package_identifier, "role": role},
        }

    return project.update_from_dict(local)


def default_app_package(project_name: str):
    user = clean_identifier(get_env_username() or DEFAULT_USERNAME)
    return append_to_identifier(to_identifier(project_name), f"_pkg_{user}")


def default_role():
    conn = cli_context.connection
    return conn.role


def default_application(project_name: str):
    user = clean_identifier(get_env_username() or DEFAULT_USERNAME)
    return append_to_identifier(to_identifier(project_name), f"_{user}")
