import sys
from pathlib import Path
from typing import Optional

import typer
from click import UsageError

from snowcli.cli.common.snow_cli_global_context import snow_cli_global_context_manager
from snowcli.cli.common.decorators import global_options
from snowcli.output.printing import print_db_cursor


@global_options
def execute_sql(
    query: Optional[str] = typer.Option(
        None,
        "-q",
        "--query",
        help="Query to execute.",
    ),
    file: Optional[Path] = typer.Option(
        None,
        "-f",
        "--filename",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="File to execute.",
    ),
    **options
):
    """
    Executes Snowflake query.

    Query to execute can be specified using query option, filename option (all queries from file will be executed)
    or via stdin by piping output from other command. For example `cat my.sql | snow sql`.
    """
    sys_input = None

    if query and file:
        raise UsageError("Both query and file provided, please specify only one.")

    if not sys.stdin.isatty():
        sys_input = sys.stdin.read()

    if sys_input and (query or file):
        raise UsageError(
            "Can't use stdin input together with query or filename option."
        )

    if not query and not file and not sys_input:
        raise UsageError("Provide either query or filename argument")
    elif sys_input:
        sql = sys_input
    else:
        sql = query if query else file.read_text()  # type: ignore

    conn = snow_cli_global_context_manager.get_connection()

    results = conn.ctx.execute_string(
        sql_text=sql,
        remove_comments=True,
    )
    for result in results:
        print_db_cursor(result)
