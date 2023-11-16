from __future__ import annotations

from snowcli.cli.common.sql_execution import SqlExecutionMixin
from snowcli.cli.constants import ObjectType, SnowparkObjectType
from snowcli.cli.object.utils import get_plural_name
from snowflake.connector.cursor import SnowflakeCursor


class ObjectManager(SqlExecutionMixin):
    def show(self, object_type: ObjectType, like: str) -> SnowflakeCursor:
        valid_sf_name = object_type.value.replace("-", " ")
        return self._execute_query(
            f"show {get_plural_name(valid_sf_name)} like '{like}'"
        )

    def drop(self, object_type: ObjectType, name: str) -> SnowflakeCursor:
        return self._execute_query(f"drop {object_type.value} {name}")

    def describe(self, object_type: ObjectType | SnowparkObjectType, name: str):
        return self._execute_query(f"describe {object_type.value} {name}")
