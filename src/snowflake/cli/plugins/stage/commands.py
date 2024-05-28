from __future__ import annotations

import itertools
from os import path
from pathlib import Path
from typing import List, Optional

import click
import typer
from snowflake.cli.api.commands.flags import (
    OnErrorOption,
    PatternOption,
    VariablesOption,
    like_option,
)
from snowflake.cli.api.commands.snow_typer import SnowTyper
from snowflake.cli.api.console import cli_console
from snowflake.cli.api.constants import ObjectType
from snowflake.cli.api.output.types import (
    CollectionResult,
    CommandResult,
    ObjectResult,
    QueryResult,
    SingleQueryResult,
)
from snowflake.cli.api.utils.path_utils import is_stage_path
from snowflake.cli.plugins.object.command_aliases import (
    add_object_command_aliases,
    scope_option,
)
from snowflake.cli.plugins.stage.diff import DiffResult, compute_stage_diff
from snowflake.cli.plugins.stage.manager import OnErrorType, StageManager

StageNameArgument = typer.Argument(..., help="Name of the stage.", show_default=False)

app = SnowTyper(
    name="stage",
    help="Manages stages.",
)

add_object_command_aliases(
    app=app,
    object_type=ObjectType.STAGE,
    name_argument=StageNameArgument,
    like_option=like_option(
        help_example='`list --like "my%"` lists all stages that begin with “my”',
    ),
    scope_option=scope_option(help_example="`list --in database my_db`"),
)


@app.command("list-files", requires_connection=True)
def stage_list_files_cmd(
    stage_name: str = StageNameArgument, pattern=PatternOption, **options
) -> CommandResult:
    """
    Lists the stage contents.
    """
    return stage_list_files(stage_name, pattern, **options)


@app.command("copy", requires_connection=True)
def copy_cmd(
    source_path: str = typer.Argument(
        help="Source path for copy operation. Can be either stage path or local.",
        show_default=False,
    ),
    destination_path: str = typer.Argument(
        help="Target directory path for copy operation. Should be stage if source is local or local if source is stage.",
        show_default=False,
    ),
    overwrite: bool = typer.Option(
        False,
        help="Overwrites existing files in the target path.",
    ),
    parallel: int = typer.Option(
        4,
        help="Number of parallel threads to use when uploading files.",
    ),
    recursive: bool = typer.Option(
        False,
        help="Copy files recursively with directory structure.",
    ),
    **options,
) -> CommandResult:
    """
    Copies all files from target path to target directory. This works for both uploading
    to and downloading files from the stage.
    """
    return copy(
        source_path=source_path,
        destination_path=destination_path,
        overwrite=overwrite,
        parallel=parallel,
        recursive=recursive,
        **options,
    )


@app.command("create", requires_connection=True)
def stage_create_cmd(stage_name: str = StageNameArgument, **options) -> CommandResult:
    """
    Creates a named stage if it does not already exist.
    """
    return stage_create(stage_name=stage_name, **options)


@app.command("remove", requires_connection=True)
def stage_remove_cmd(
    stage_name: str = StageNameArgument,
    file_name: str = typer.Argument(
        ...,
        help="Name of the file to remove.",
        show_default=False,
    ),
    **options,
) -> CommandResult:
    """
    Removes a file from a stage.
    """
    return stage_remove(stage_name=stage_name, file_name=file_name, **options)


@app.command("diff", hidden=True, requires_connection=True)
def stage_diff_cmd(
    stage_name: str = typer.Argument(
        help="Fully qualified name of a stage",
        show_default=False,
    ),
    folder_name: str = typer.Argument(
        help="Path to local folder",
        show_default=False,
    ),
    **options,
) -> ObjectResult:
    """
    Diffs a stage with a local folder.
    """
    return stage_diff(stage_name=stage_name, folder_name=folder_name, **options)


@app.command("execute", requires_connection=True)
def execute_cmd(
    stage_path: str = typer.Argument(
        ...,
        help="Stage path with files to be execute. For example `@stage/dev/*`.",
        show_default=False,
    ),
    on_error: OnErrorType = OnErrorOption,
    variables: Optional[List[str]] = VariablesOption,
    **options,
) -> CollectionResult:
    """
    Execute immediate all files from the stage path. Files can be filtered with glob like pattern,
    e.g. `@stage/*.sql`, `@stage/dev/*`. Only files with `.sql` extension will be executed.
    """
    return execute(
        stage_path=stage_path, on_error=on_error, variables=variables, **options
    )


def stage_list_files(
    stage_name: str, pattern: Optional[str], **options
) -> CommandResult:
    cursor = StageManager().list_files(stage_name=stage_name, pattern=pattern)
    return QueryResult(cursor)


def copy(
    source_path: str = typer.Argument(
        help="Source path for copy operation. Can be either stage path or local.",
        show_default=False,
    ),
    destination_path: str = typer.Argument(
        help="Target directory path for copy operation. Should be stage if source is local or local if source is stage.",
        show_default=False,
    ),
    overwrite: bool = typer.Option(
        False,
        help="Overwrites existing files in the target path.",
    ),
    parallel: int = typer.Option(
        4,
        help="Number of parallel threads to use when uploading files.",
    ),
    recursive: bool = typer.Option(
        False,
        help="Copy files recursively with directory structure.",
    ),
    **options,
) -> CommandResult:
    is_get = is_stage_path(source_path)
    is_put = is_stage_path(destination_path)

    if is_get and is_put:
        raise click.ClickException(
            "Both source and target path are remote. This operation is not supported."
        )
    if not is_get and not is_put:
        raise click.ClickException(
            "Both source and target path are local. This operation is not supported."
        )

    if is_get:
        return get(
            recursive=recursive,
            source_path=source_path,
            destination_path=destination_path,
            parallel=parallel,
        )
    return _put(
        recursive=recursive,
        source_path=source_path,
        destination_path=destination_path,
        parallel=parallel,
        overwrite=overwrite,
    )


def stage_create(stage_name: str, **options) -> CommandResult:
    cursor = StageManager().create(stage_name=stage_name)
    return SingleQueryResult(cursor)


def stage_remove(stage_name: str, file_name: str, **options) -> CommandResult:
    cursor = StageManager().remove(stage_name=stage_name, path=file_name)
    return SingleQueryResult(cursor)


def stage_diff(
    stage_name: str,
    folder_name: str,
    **options,
) -> ObjectResult:
    """
    Diffs a stage with a local folder.
    """

    diff: DiffResult = compute_stage_diff(Path(folder_name), stage_name)
    return ObjectResult(str(diff))


def execute(
    stage_path: str, on_error: OnErrorType, variables: Optional[List[str]], **options
) -> CollectionResult:
    """
    Execute immediate all files from the stage path. Files can be filtered with glob like pattern,
    e.g. `@stage/*.sql`, `@stage/dev/*`. Only files with `.sql` extension will be executed.
    """

    results = StageManager().execute(
        stage_path=stage_path, on_error=on_error, variables=variables
    )
    return CollectionResult(results)


def get(recursive: bool, source_path: str, destination_path: str, parallel: int):
    target = Path(destination_path).resolve()
    if not recursive:
        cli_console.warning(
            "Use `--recursive` flag, which copy files recursively with directory structure. This will be the default behavior in the future."
        )
        cursor = StageManager().get(
            stage_path=source_path, dest_path=target, parallel=parallel
        )
        return QueryResult(cursor)

    cursors = StageManager().get_recursive(
        stage_path=source_path, dest_path=target, parallel=parallel
    )
    results = [list(QueryResult(c).result) for c in cursors]
    flattened_results = list(itertools.chain.from_iterable(results))
    sorted_results = sorted(
        flattened_results,
        key=lambda e: (path.dirname(e["file"]), path.basename(e["file"])),
    )
    return CollectionResult(sorted_results)


def _put(
    recursive: bool,
    source_path: str,
    destination_path: str,
    parallel: int,
    overwrite: bool,
):
    if recursive:
        raise click.ClickException("Recursive flag for upload is not supported.")

    source = Path(source_path).resolve()
    local_path = str(source) + "/*" if source.is_dir() else str(source)

    cursor = StageManager().put(
        local_path=local_path,
        stage_path=destination_path,
        overwrite=overwrite,
        parallel=parallel,
    )
    return QueryResult(cursor)
