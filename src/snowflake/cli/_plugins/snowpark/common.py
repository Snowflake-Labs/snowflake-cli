# Copyright (c) 2024 Snowflake Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Dict, List, Set

from click import UsageError
from snowflake.cli._plugins.snowpark.models import Requirement
from snowflake.cli._plugins.snowpark.snowpark_entity_model import (
    ProcedureEntityModel,
    SnowparkEntityModel,
)
from snowflake.cli._plugins.snowpark.snowpark_project_paths import Artefact
from snowflake.cli.api.console import cli_console
from snowflake.cli.api.constants import (
    INIT_TEMPLATE_VARIABLE_CLOSING,
    INIT_TEMPLATE_VARIABLE_OPENING,
    PROJECT_TEMPLATE_VARIABLE_CLOSING,
    PROJECT_TEMPLATE_VARIABLE_OPENING,
    ObjectType,
)
from snowflake.cli.api.sql_execution import SqlExecutionMixin
from snowflake.connector.cursor import SnowflakeCursor

log = logging.getLogger(__name__)

SnowparkEntities = Dict[str, SnowparkEntityModel]
StageToArtefactMapping = Dict[str, set[Artefact]]
EntityToImportPathsMapping = Dict[str, set[str]]

DEFAULT_RUNTIME = "3.10"


class SnowparkObject(Enum):
    """This clas is used only for Snowpark execute where choice is limited."""

    PROCEDURE = str(ObjectType.PROCEDURE)
    FUNCTION = str(ObjectType.FUNCTION)


class SnowparkObjectManager(SqlExecutionMixin):
    def execute(
        self, execution_identifier: str, object_type: SnowparkObject
    ) -> SnowflakeCursor:
        if object_type == SnowparkObject.FUNCTION:
            return self._execute_query(f"select {execution_identifier}")
        if object_type == SnowparkObject.PROCEDURE:
            return self._execute_query(f"call {execution_identifier}")
        raise UsageError(f"Unknown object type: {object_type}.")

    def create_or_replace(
        self,
        entity: SnowparkEntityModel,
        artifact_files: set[str],
        snowflake_dependencies: list[str],
    ) -> str:
        entity.imports.extend(artifact_files)
        imports = [f"'{x}'" for x in entity.imports]
        packages_list = ",".join(f"'{p}'" for p in snowflake_dependencies)

        object_type = entity.get_type()

        query = [
            f"create or replace {object_type} {entity.udf_sproc_identifier.identifier_for_sql}",
            f"copy grants",
            f"returns {entity.returns}",
            "language python",
            f"runtime_version={entity.runtime or DEFAULT_RUNTIME}",
            f"imports=({', '.join(imports)})",
            f"handler='{entity.handler}'",
            f"packages=({packages_list})",
        ]

        if entity.external_access_integrations:
            query.append(entity.get_external_access_integrations_sql())

        if entity.secrets:
            query.append(entity.get_secrets_sql())

        if isinstance(entity, ProcedureEntityModel) and entity.execute_as_caller:
            query.append("execute as caller")

        return self._execute_query("\n".join(query))

    def deploy_entity(
        self,
        entity: SnowparkEntityModel,
        existing_objects: Dict[str, SnowflakeCursor],
        snowflake_dependencies: List[str],
        entities_to_artifact_map: EntityToImportPathsMapping,
    ):
        cli_console.step(f"Creating {entity.type} {entity.fqn}")
        object_exists = entity.entity_id in existing_objects
        replace_object = False
        if object_exists:
            replace_object = _check_if_replace_is_required(
                entity=entity,
                current_state=existing_objects[entity.entity_id],
                snowflake_dependencies=snowflake_dependencies,
                stage_artifact_files=entities_to_artifact_map[entity.entity_id],
            )

        state = {
            "object": entity.udf_sproc_identifier.identifier_with_arg_names_types_defaults,
            "type": entity.get_type(),
        }
        if object_exists and not replace_object:
            return {**state, "status": "packages updated"}

        self.create_or_replace(
            entity=entity,
            artifact_files=entities_to_artifact_map[entity.entity_id],
            snowflake_dependencies=snowflake_dependencies,
        )
        return {
            **state,
            "status": "created" if not object_exists else "definition updated",
        }


def _check_if_replace_is_required(
    entity: SnowparkEntityModel,
    current_state,
    snowflake_dependencies: List[str],
    stage_artifact_files: set[str],
) -> bool:
    object_type = entity.get_type()
    resource_json = _convert_resource_details_to_dict(current_state)
    old_dependencies = resource_json["packages"]

    if _snowflake_dependencies_differ(old_dependencies, snowflake_dependencies):
        log.info(
            "Found difference of package requirements. Replacing the %s.", object_type
        )
        return True

    if set(entity.external_access_integrations) != set(
        resource_json.get("external_access_integrations", [])
    ):
        log.info(
            "Found difference of external access integrations. Replacing the %s.",
            object_type,
        )
        return True

    if (
        resource_json["handler"].lower() != entity.handler.lower()
        or resource_json["returns"].lower()
        != user_to_sql_type_mapper(entity.returns).lower()
    ):
        log.info(
            "Return type or handler types do not match. Replacing the %s.", object_type
        )
        return True

    if _compare_imports(resource_json, entity.imports, stage_artifact_files):
        log.info("Imports do not match. Replacing the %s", object_type)
        return True

    if entity.runtime is not None and entity.runtime != resource_json.get(
        "runtime_version", "RUNTIME_NOT_SET"
    ):
        log.info("Runtime versions do not match. Replacing the %s", object_type)
        return True

    if isinstance(entity, ProcedureEntityModel):
        if resource_json.get("execute as", "OWNER") != (
            "CALLER" if entity.execute_as_caller else "OWNER"
        ):
            log.info(
                "Execute as caller settings do not match. Replacing the %s", object_type
            )
            return True

    return False


def _convert_resource_details_to_dict(function_details: SnowflakeCursor) -> dict:
    import json

    function_dict = {}
    json_properties = ["packages", "installed_packages"]
    for function in function_details:
        if function[0] in json_properties:
            function_dict[function[0]] = json.loads(
                function[1].replace("'", '"'),
            )
        else:
            function_dict[function[0]] = function[1]
    return function_dict


def _snowflake_dependencies_differ(
    old_dependencies: List[str], new_dependencies: List[str]
) -> bool:
    def _standardize(packages: List[str]) -> Set[str]:
        return set(
            Requirement.parse_line(package).name_and_version for package in packages
        )

    return _standardize(old_dependencies) != _standardize(new_dependencies)


def user_to_sql_type_mapper(user_provided_type: str) -> str:
    def _cast(user_type: str, sql_type: str, default: str) -> str | None:
        if user_type == sql_type:
            # TEXT -> VARCHAR(16777216)
            return default
        if user_type.startswith(sql_type):
            # TEXT(30) -> VARCHAR(30)
            return user_type.replace(sql_type, "VARCHAR")
        return None

    mapping = {
        ("VARCHAR", "(16777216)"): ("CHAR", "TEXT", "STRING"),
        ("BINARY", "(8388608)"): ("BINARY", "VARBINARY"),
        ("NUMBER", "(38,0)"): (
            "NUMBER",
            "DECIMAL",
            "INT",
            "INTEGER",
            "BIGINT",
            "SMALLINT",
            "TINYINT",
            "BYTEINT",
        ),
        ("FLOAT", ""): (
            "FLOAT",
            "DOUBLE",
            "DOUBLE PRECISION",
            "REAL",
            "FLOAT",
            "FLOAT4",
            "FLOAT8",
        ),
        ("TIMESTAMP_NTZ", ""): ("TIMESTAMP_NTZ", "TIMESTAMPNTZ", "DATETIME"),
        ("TIMESTAMP_LTZ", ""): ("TIMESTAMP_LTZ", "TIMESTAMPLTZ"),
        ("TIMESTAMP_TZ", ""): ("TIMESTAMP_TZ", "TIMESTAMPTZ"),
    }

    user_provided_type = user_provided_type.upper()
    for (cast_type, default), matching_types in mapping.items():
        for type_ in matching_types:
            if user_provided_type == type_:
                # TEXT -> VARCHAR(16777216)
                return default
            if user_provided_type.startswith(type_):
                # TEXT(30) -> VARCHAR(30)
                return user_provided_type.replace(type_, cast_type + default)
    return user_provided_type


def _compare_imports(
    resource_json: dict, imports: List[str], artifact_files: set[str]
) -> bool:
    pattern = re.compile(r"(?:\[@?\w+_\w+\.)?(\w+(?:/\w+)+\.\w+)(?:\])?")

    project_imports = {
        imp
        for import_string in [*imports, *artifact_files]
        for imp in pattern.findall(import_string.lower())
    }

    if "imports" not in resource_json.keys():
        object_imports = set()
    else:
        object_imports = {
            imp.lower()
            for imp in pattern.findall(resource_json.get("imports", "").lower())
        }

    return project_imports != object_imports


def is_name_a_templated_one(name: str) -> bool:
    return (
        PROJECT_TEMPLATE_VARIABLE_OPENING in name
        and PROJECT_TEMPLATE_VARIABLE_CLOSING in name
    ) or (
        INIT_TEMPLATE_VARIABLE_OPENING in name
        and INIT_TEMPLATE_VARIABLE_CLOSING in name
    )
