from __future__ import annotations

from typing import Dict, List

from pydantic import Field, field_validator
from snowflake.cli.api.project.schemas.snowpark.argument import Argument
from snowflake.cli.api.project.schemas.updatable_model import (
    IdentifierField,
    UpdatableModel,
)


class Callable(UpdatableModel):
    name: str = Field(
        title="Object identifier"
    )  # TODO: implement validator. If a name is filly qualified, database and schema cannot be specified
    database: str | None = IdentifierField(
        title="Name of the database for the function or procedure", default=None
    )

    schema_name: str | None = IdentifierField(
        title="Name of the schema for the function or procedure",
        default=None,
        alias="schema",
    )
    handler: str = Field(
        title="Function’s or procedure’s implementation of the object inside source module",
        examples=["functions.hello_function"],
    )
    returns: str = Field(
        title="Type of the result"
    )  # TODO: again, consider Literal/Enum
    signature: str | List[Argument] = Field(
        title="The signature parameter describes consecutive arguments passed to the object"
    )
    runtime: str | float | None = Field(
        title="Python version to use when executing ", default=None
    )
    external_access_integrations: List[str] | None = Field(
        title="Names of external access integrations needed for this procedure’s handler code to access external networks",
        default=[],
    )
    secrets: Dict[str, str] | None = Field(
        title="Assigns the names of secrets to variables so that you can use the variables to reference the secrets",
        default=[],
    )
    imports: List[str] | None = Field(
        title="Stage and path to previously uploaded files you want to import",
        default=[],
    )

    @field_validator("runtime")
    @classmethod
    def convert_runtime(cls, runtime_input: str | float) -> str:
        if isinstance(runtime_input, float):
            return str(runtime_input)
        return runtime_input


class FunctionSchema(Callable):
    pass


class ProcedureSchema(Callable):
    execute_as_caller: bool | None = Field(
        title="Determine whether the procedure is executed with the privileges of the owner (you) or with the privileges of the caller",
        default=False,
    )
