import functools
from pathlib import Path

from snowflake.cli.api.cli_global_context import get_cli_context
from snowflake.cli.api.console import cli_console as cc
from snowflake.cli.api.entities.actions import EntityAction
from snowflake.cli.api.entities.actions.lib import ActionContext
from snowflake.cli.api.entities.common import get_sql_executor
from snowflake.cli.api.entities.entity_base import EntityBase
from snowflake.cli.api.exceptions import InvalidProjectDefinitionVersionError
from snowflake.cli.api.project.definition import default_role
from snowflake.cli.api.project.schemas.entities.entities import (
    v2_entity_model_to_entity_map,
)
from snowflake.cli.api.project.schemas.project_definition import (
    DefinitionV20,
    ProjectDefinition,
)
from snowflake.cli.api.project.util import to_identifier


class WorkspaceManager:
    """
    Instantiates entity instances from entity models, providing higher-order functionality on entity compositions.
    """

    def __init__(self, project_definition: ProjectDefinition, project_root: Path):
        if not project_definition.meets_version_requirement("2"):
            raise InvalidProjectDefinitionVersionError(
                "2.x", project_definition.definition_version
            )
        self._project_definition: DefinitionV20 = project_definition
        self._project_root = project_root
        self._default_role = default_role()
        if self._default_role is None:
            self._default_role = get_sql_executor().current_role()
        self.default_warehouse = None
        cli_context = get_cli_context()
        if cli_context.connection.warehouse:
            self.default_warehouse = to_identifier(cli_context.connection.warehouse)

    def _get_model(self, entity_id: str):
        entity_model = self._project_definition.entities.get(entity_id, None)
        if entity_model is None:
            raise ValueError(f"No such entity ID: {entity_id}")
        return entity_model

    @functools.cache
    def get_entity(self, entity_id: str) -> EntityBase:
        """
        Returns an entity instance with the given ID. If exists, reuses the
        previously returned instance, or instantiates a new one otherwise.
        """
        entity_model = self._get_model(entity_id)
        entity_model_cls = entity_model.__class__
        entity_cls = v2_entity_model_to_entity_map[entity_model_cls]
        return entity_cls(entity_model)

    def perform_action(self, entity_id: str, action: EntityAction, *args, **kwargs):
        """
        Instantiates an entity of the given ID and calls the given action on it.
        """
        entity = self.get_entity(entity_id)
        if entity.supports(action):
            fn = entity.get_action_callable(action)
            ctx = ActionContext(
                console=cc,
                project_root=self.project_root(),
                default_role=self._default_role,
                default_warehouse=self.default_warehouse,
            )
            return fn(ctx, *args, **kwargs)
        else:
            raise ValueError(f'This entity type does not support "{action.value}"')

    def project_root(self) -> Path:
        return self._project_root
