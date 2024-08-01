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
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

import typer
from click import ClickException
from snowflake.cli.api.cli_global_context import get_cli_context
from snowflake.cli.api.commands.decorators import (
    with_project_definition,
)
from snowflake.cli.api.commands.flags import (
    ReplaceOption,
    execution_identifier_argument,
    identifier_argument,
    like_option,
)
from snowflake.cli.api.commands.snow_typer import SnowTyperFactory
from snowflake.cli.api.constants import (
    DEFAULT_SIZE_LIMIT_MB,
    DEPLOYMENT_STAGE,
    ObjectType,
)
from snowflake.cli.api.exceptions import (
    NoProjectDefinitionError,
    SecretsWithoutExternalAccessIntegrationError,
)
from snowflake.cli.api.identifiers import FQN
from snowflake.cli.api.output.types import (
    CollectionResult,
    CommandResult,
    MessageResult,
    SingleQueryResult,
)
from snowflake.cli.api.project.schemas.entities.snowpark_entity import SnowparkEntity
from snowflake.cli.api.project.schemas.project_definition import (
    ProjectDefinition,
    ProjectDefinitionV2,
)
from snowflake.cli.api.project.schemas.snowpark.callable import (
    FunctionSchema,
    ProcedureSchema,
)
from snowflake.cli.api.secure_path import SecurePath
from snowflake.cli.plugins.object.commands import (
    describe as object_describe,
)
from snowflake.cli.plugins.object.commands import (
    drop as object_drop,
)
from snowflake.cli.plugins.object.commands import (
    list_ as object_list,
)
from snowflake.cli.plugins.object.commands import (
    scope_option,
)
from snowflake.cli.plugins.object.manager import ObjectManager
from snowflake.cli.plugins.snowpark import package_utils
from snowflake.cli.plugins.snowpark.common import (
    UdfSprocIdentifier,
    check_if_replace_is_required,
)
from snowflake.cli.plugins.snowpark.manager import FunctionManager, ProcedureManager
from snowflake.cli.plugins.snowpark.package.anaconda_packages import (
    AnacondaPackages,
    AnacondaPackagesManager,
)
from snowflake.cli.plugins.snowpark.package.commands import app as package_app
from snowflake.cli.plugins.snowpark.snowpark_package_paths import SnowparkPackagePaths
from snowflake.cli.plugins.snowpark.snowpark_shared import (
    AllowSharedLibrariesOption,
    IgnoreAnacondaOption,
    IndexUrlOption,
    SkipVersionCheckOption,
)
from snowflake.cli.plugins.snowpark.zipper import zip_dir
from snowflake.cli.plugins.stage.manager import StageManager
from snowflake.connector import DictCursor, ProgrammingError

log = logging.getLogger(__name__)

app = SnowTyperFactory(
    name="snowpark",
    help="Manages procedures and functions.",
)
app.add_typer(package_app)

ObjectTypeArgument = typer.Argument(
    help="Type of Snowpark object",
    case_sensitive=False,
    show_default=False,
)
IdentifierArgument = identifier_argument(
    "function/procedure",
    example="hello(int, string)",
)
LikeOption = like_option(
    help_example='`list function --like "my%"` lists all functions that begin with “my”',
)


@app.command("deploy", requires_connection=True)
@with_project_definition()
def deploy(
    replace: bool = ReplaceOption(
        help="Replaces procedure or function, even if no detected changes to metadata"
    ),
    **options,
) -> CommandResult:
    """
    Deploys procedures and functions defined in project. Deploying the project alters all objects defined in it.
    By default, if any of the objects exist already the commands will fail unless `--replace` flag is provided.
    All deployed objects use the same artifact which is deployed only once.
    """
    cli_context = get_cli_context()
    pd = cli_context.project_definition
    if not pd.meets_version_requirement("2"):
        pd = _migrate_v1_snowpark_to_v2(pd)

    paths = SnowparkPackagePaths.for_snowpark_project(
        project_root=SecurePath(cli_context.project_root),
        snowpark_project_definition=pd,
    )

    procedures = pd.get_entities_by_type("procedure")
    functions = pd.get_entities_by_type("function")

    if not procedures and not functions:
        raise ClickException(
            "No procedures or functions were specified in the project definition."
        )

    if not paths.artifact_file.exists():
        raise ClickException(
            "Artifact required for deploying the project does not exist in this directory. "
            "Please use build command to create it."
        )

    pm = ProcedureManager()
    fm = FunctionManager()
    om = ObjectManager()

    _assert_object_definitions_are_correct("function", functions)
    _assert_object_definitions_are_correct("procedure", procedures)
    _check_if_all_defined_integrations_exists(om, functions, procedures)

    existing_functions = _find_existing_objects(ObjectType.FUNCTION, functions, om)
    existing_procedures = _find_existing_objects(ObjectType.PROCEDURE, procedures, om)

    if (existing_functions or existing_procedures) and not replace:
        msg = "Following objects already exists. Consider using --replace.\n"
        msg += "\n".join(f"function: {n}" for n in existing_functions)
        msg += "\n" if existing_functions and existing_procedures else ""
        msg += "\n".join(f"procedure: {n}" for n in existing_procedures)
        raise ClickException(msg)

    # Create stage
    snowflake_dependencies = _read_snowflake_requrements_file(
        paths.snowflake_requirements_file
    )
    stage_names = {
        entity.stage for entity in [*functions.values(), *procedures.values()]
    }
    stage_manager = StageManager()
    project_name = (
        pd.defaults.project_name if pd.defaults.project_name else "my_snowpark_project"
    )
    for stage in stage_names:
        stage = FQN.from_string(stage).using_context()
        stage_manager.create(
            stage_name=stage, comment="deployments managed by Snowflake CLI"
        )
        artifact_stage_directory = get_app_stage_path(stage, project_name)
    artifact_stage_target = (
        f"{artifact_stage_directory}/{paths.artifact_file.path.name}"
    )

    stage_manager.put(
        local_path=paths.artifact_file.path,
        stage_path=artifact_stage_directory,
        overwrite=True,
    )

    deploy_status = []
    # Procedures
    for procedure in [*procedures.values()]:
        operation_result = _deploy_single_object(
            manager=pm,
            object_type=ObjectType.PROCEDURE,
            object_definition=procedure,
            existing_objects=existing_procedures,
            snowflake_dependencies=snowflake_dependencies,
            stage_artifact_path=artifact_stage_target,
        )
        deploy_status.append(operation_result)

    # Functions
    for function in [*functions.values()]:
        operation_result = _deploy_single_object(
            manager=fm,
            object_type=ObjectType.FUNCTION,
            object_definition=function,
            existing_objects=existing_functions,
            snowflake_dependencies=snowflake_dependencies,
            stage_artifact_path=artifact_stage_target,
        )
        deploy_status.append(operation_result)

    return CollectionResult(deploy_status)


def _assert_object_definitions_are_correct(
    object_type, object_definitions: Dict[str, SnowparkEntity]
):
    for name, definition in object_definitions.items():
        database = definition.database
        schema = definition.schema_name
        name = definition.name
        fqn_parts = len(name.split("."))
        if fqn_parts == 3 and database:
            raise ClickException(
                f"database of {object_type} {name} is redefined in its name"
            )
        if fqn_parts >= 2 and schema:
            raise ClickException(
                f"schema of {object_type} {name} is redefined in its name"
            )


def _find_existing_objects(
    object_type: ObjectType,
    objects: Dict[str, SnowparkEntity],
    om: ObjectManager,
):
    existing_objects = {}
    for object_name, object_definition in objects.items():
        identifier = UdfSprocIdentifier.from_definition(
            object_definition
        ).identifier_with_arg_types
        try:
            current_state = om.describe(
                object_type=object_type.value.sf_name,
                name=identifier,
            )
            existing_objects[identifier] = current_state
        except ProgrammingError:
            pass
    return existing_objects


def _check_if_all_defined_integrations_exists(
    om: ObjectManager,
    functions: Dict[str, FunctionSchema],
    procedures: Dict[str, ProcedureSchema],
):
    existing_integrations = {
        i["name"].lower()
        for i in om.show(object_type="integration", cursor_class=DictCursor, like=None)
        if i["type"] == "EXTERNAL_ACCESS"
    }
    declared_integration: Set[str] = set()
    for object_definition in [*functions.values(), *procedures.values()]:
        external_access_integrations = {
            s.lower() for s in object_definition.external_access_integrations
        }
        secrets = [s.lower() for s in object_definition.secrets]

        if not external_access_integrations and secrets:
            raise SecretsWithoutExternalAccessIntegrationError(object_definition.name)

        declared_integration = declared_integration | external_access_integrations

    missing = declared_integration - existing_integrations
    if missing:
        raise ClickException(
            f"Following external access integration does not exists in Snowflake: {', '.join(missing)}"
        )


def get_app_stage_path(stage_name: Optional[str], project_name: str) -> str:
    artifact_stage_directory = f"@{(stage_name or DEPLOYMENT_STAGE)}/{project_name}"
    return artifact_stage_directory


def _deploy_single_object(
    manager: FunctionManager | ProcedureManager,
    object_type: ObjectType,
    object_definition: SnowparkEntity,
    existing_objects: Dict[str, Dict],
    snowflake_dependencies: List[str],
    stage_artifact_path: str,
):

    identifiers = UdfSprocIdentifier.from_definition(object_definition)

    log.info(
        "Deploying %s: %s", object_type, identifiers.identifier_with_arg_names_types
    )

    handler = object_definition.handler
    returns = object_definition.returns
    imports = object_definition.imports
    external_access_integrations = object_definition.external_access_integrations
    runtime_ver = object_definition.runtime
    execute_as_caller = None
    if object_type == ObjectType.PROCEDURE:
        execute_as_caller = object_definition.execute_as_caller
    replace_object = False

    object_exists = identifiers.identifier_with_arg_types in existing_objects
    if object_exists:
        replace_object = check_if_replace_is_required(
            object_type=object_type,
            current_state=existing_objects[identifiers.identifier_with_arg_types],
            handler=handler,
            return_type=returns,
            snowflake_dependencies=snowflake_dependencies,
            external_access_integrations=external_access_integrations,
            imports=imports,
            stage_artifact_file=stage_artifact_path,
            runtime_ver=runtime_ver,
            execute_as_caller=execute_as_caller,
        )

    if object_exists and not replace_object:
        return {
            "object": identifiers.identifier_with_arg_names_types_defaults,
            "type": str(object_type),
            "status": "packages updated",
        }

    create_or_replace_kwargs = {
        "identifier": identifiers,
        "handler": handler,
        "return_type": returns,
        "artifact_file": stage_artifact_path,
        "packages": snowflake_dependencies,
        "runtime": object_definition.runtime,
        "external_access_integrations": object_definition.external_access_integrations,
        "secrets": object_definition.secrets,
        "imports": imports,
    }
    if object_type == ObjectType.PROCEDURE:
        create_or_replace_kwargs[
            "execute_as_caller"
        ] = object_definition.execute_as_caller
    manager.create_or_replace(**create_or_replace_kwargs)

    status = "created" if not object_exists else "definition updated"
    return {
        "object": identifiers.identifier_with_arg_names_types_defaults,
        "type": str(object_type),
        "status": status,
    }


def _read_snowflake_requrements_file(file_path: SecurePath):
    if not file_path.exists():
        return []
    return file_path.read_text(file_size_limit_mb=DEFAULT_SIZE_LIMIT_MB).splitlines()


@app.command("build", requires_connection=True)
@with_project_definition()
def build(
    ignore_anaconda: bool = IgnoreAnacondaOption,
    allow_shared_libraries: bool = AllowSharedLibrariesOption,
    index_url: Optional[str] = IndexUrlOption,
    skip_version_check: bool = SkipVersionCheckOption,
    **options,
) -> CommandResult:
    """
    Builds the Snowpark project as a `.zip` archive that can be used by `deploy` command.
    The archive is built using only the `src` directory specified in the project file.
    """
    cli_context = get_cli_context()
    pd = cli_context.project_definition
    if not pd.meets_version_requirement("2"):
        pd = _migrate_v1_snowpark_to_v2(pd)

    snowpark_paths = SnowparkPackagePaths.for_snowpark_project(
        project_root=SecurePath(cli_context.project_root),
        snowpark_project_definition=pd,
    )
    log.info("Building package using sources from:")
    log.info(",".join(str(s) for s in snowpark_paths.sources))

    anaconda_packages_manager = AnacondaPackagesManager()

    with SecurePath.temporary_directory() as packages_dir:
        if snowpark_paths.defined_requirements_file.exists():
            log.info("Resolving any requirements from requirements.txt...")
            requirements = package_utils.parse_requirements(
                requirements_file=snowpark_paths.defined_requirements_file,
            )
            anaconda_packages = (
                AnacondaPackages.empty()
                if ignore_anaconda
                else anaconda_packages_manager.find_packages_available_in_snowflake_anaconda()
            )
            download_result = package_utils.download_unavailable_packages(
                requirements=requirements,
                target_dir=packages_dir,
                anaconda_packages=anaconda_packages,
                skip_version_check=skip_version_check,
                pip_index_url=index_url,
            )
            if not download_result.succeeded:
                raise ClickException(download_result.error_message)

            log.info("Checking to see if packages have shared (.so/.dll) libraries...")
            if package_utils.detect_and_log_shared_libraries(
                download_result.downloaded_packages_details
            ):
                if not allow_shared_libraries:
                    raise ClickException(
                        "Some packages contain shared (.so/.dll) libraries. "
                        "Try again with --allow-shared-libraries."
                    )
            if download_result.anaconda_packages:
                anaconda_packages.write_requirements_file_in_snowflake_format(  # type: ignore
                    file_path=snowpark_paths.snowflake_requirements_file,
                    requirements=download_result.anaconda_packages,
                )

        zip_dir(
            source=snowpark_paths.sources_paths,
            dest_zip=snowpark_paths.artifact_file.path,
        )
        if any(packages_dir.iterdir()):
            # if any packages were generated, append them to the .zip
            zip_dir(
                source=packages_dir.path,
                dest_zip=snowpark_paths.artifact_file.path,
                mode="a",
            )

    log.info("Package now ready: %s", snowpark_paths.artifact_file.path)

    return MessageResult(
        f"Build done. Artifact path: {snowpark_paths.artifact_file.path}"
    )


class _SnowparkObject(Enum):
    """This clas is used only for Snowpark execute where choice is limited."""

    PROCEDURE = str(ObjectType.PROCEDURE)
    FUNCTION = str(ObjectType.FUNCTION)


def _execute_object_method(
    method_name: str,
    object_type: _SnowparkObject,
    **kwargs,
):
    if object_type == _SnowparkObject.PROCEDURE:
        manager = ProcedureManager()
    elif object_type == _SnowparkObject.FUNCTION:
        manager = FunctionManager()
    else:
        raise ClickException(f"Unknown object type: {object_type}")

    return getattr(manager, method_name)(**kwargs)


@app.command("execute", requires_connection=True)
def execute(
    object_type: _SnowparkObject = ObjectTypeArgument,
    execution_identifier: str = execution_identifier_argument(
        "procedure/function", "hello(1, 'world')"
    ),
    **options,
) -> CommandResult:
    """Executes a procedure or function in a specified environment."""
    cursor = _execute_object_method(
        "execute", object_type=object_type, execution_identifier=execution_identifier
    )
    return SingleQueryResult(cursor)


@app.command("list", requires_connection=True)
def list_(
    object_type: _SnowparkObject = ObjectTypeArgument,
    like: str = LikeOption,
    scope: Tuple[str, str] = scope_option(
        help_example="`list function --in database my_db`"
    ),
    **options,
):
    """Lists all available procedures or functions."""
    object_list(object_type=object_type.value, like=like, scope=scope, **options)


@app.command("drop", requires_connection=True)
def drop(
    object_type: _SnowparkObject = ObjectTypeArgument,
    identifier: str = IdentifierArgument,
    **options,
):
    """Drop procedure or function."""
    object_drop(object_type=object_type.value, object_name=identifier, **options)


@app.command("describe", requires_connection=True)
def describe(
    object_type: _SnowparkObject = ObjectTypeArgument,
    identifier: str = IdentifierArgument,
    **options,
):
    """Provides description of a procedure or function."""
    object_describe(object_type=object_type.value, object_name=identifier, **options)


def _migrate_v1_snowpark_to_v2(pd: ProjectDefinition):
    if not pd.snowpark:
        raise NoProjectDefinitionError(
            project_type="snowpark", project_file=get_cli_context().project_root
        )

    data: dict = {
        "definition_version": "2",
        "defaults": {
            "stage": pd.snowpark.stage_name,
            "project_name": pd.snowpark.project_name,
        },
        "entities": {},
    }
    # TODO: think how to join those two loops
    for function in pd.snowpark.functions:
        function_dict = {
            "type": "function",
            "stage": pd.snowpark.stage_name,
            "src": pd.snowpark.src,
            "handler": function.handler,
            "returns": function.returns,
            "signature": function.signature,
            "runtime": function.runtime,
            "external_access_integrations": function.external_access_integrations,
            "secrets": function.secrets,
            "imports": function.imports,
            "name": function.name,
            "database": function.database,
            "schema": function.schema_name,
        }
        data["entities"][function.name] = function_dict

    for procedure in pd.snowpark.procedures:
        procedure_dict = {
            "type": "procedure",
            "stage": pd.snowpark.stage_name,
            "src": pd.snowpark.src,
            "handler": procedure.handler,
            "returns": procedure.returns,
            "signature": procedure.signature,
            "runtime": procedure.runtime,
            "external_access_integrations": procedure.external_access_integrations,
            "secrets": procedure.secrets,
            "imports": procedure.imports,
            "execute_as_caller": procedure.execute_as_caller,
            "name": procedure.name,
            "database": procedure.database,
            "schema": procedure.schema_name,
        }
        data["entities"][procedure.name] = procedure_dict

    return ProjectDefinitionV2(**data)
