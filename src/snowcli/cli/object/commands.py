from __future__ import annotations

from typing import cast

import typer
from click import ClickException
from snowcli.cli.common.decorators import global_options_with_connection
from snowcli.cli.common.flags import DEFAULT_CONTEXT_SETTINGS
from snowcli.cli.constants import OBJECT_TO_NAMES, ObjectNames
from snowcli.cli.object.manager import ObjectManager
from snowcli.output.decorators import with_output
from snowcli.output.types import QueryResult

app = typer.Typer(
    name="object",
    context_settings=DEFAULT_CONTEXT_SETTINGS,
    help="Manages Snowflake objects like warehouses and stages",
)
app.add_typer(stage_app)  # type: ignore


def _check_if_supported_object(value: str) -> ObjectNames:
    if value not in OBJECT_TO_NAMES:
        raise ClickException(f"Object of type {value} is not supported.")
    return OBJECT_TO_NAMES[value]


NameArgument = typer.Argument(None, help="Name of the object")
ObjectArgument = typer.Argument(
    None,
    help="Type of object. For example table, procedure, streamlit.",
    case_sensitive=False,
    callback=_check_if_supported_object,
)
LikeOption = typer.Option(
    "%%",
    "--like",
    "-l",
    help='Regular expression for filtering the functions by name. For example, `list --like "my%"` lists '
    "all functions in the **dev** (default) environment that begin with “my”.",
)


@app.command("list")
@with_output
@global_options_with_connection
def list_(
    object_type=ObjectArgument,
    like: str = LikeOption,
    **options,
):
    """Lists all available Snowflake objects of given type."""
    return QueryResult(ObjectManager().show(object_type.sf_plural_name, like))


@app.command()
@with_output
@global_options_with_connection
def drop(object_type=ObjectArgument, object_name: str = NameArgument, **options):
    """Drops Snowflake object of given name and type."""
    return QueryResult(ObjectManager().drop(object_type.sf_name, object_name))


@app.command()
@with_output
@global_options_with_connection
def describe(object_type=ObjectArgument, object_name: str = NameArgument, **options):
    """Provides description of an object of given type."""
    return QueryResult(ObjectManager().describe(object_type.sf_name, object_name))
