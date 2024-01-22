import sys
from pathlib import Path
from typing import List, Optional, Tuple

import typer

from snowflake.cli.api.commands.decorators import (
    global_options_with_connection,
    with_output,
)
from snowflake.cli.api.commands.flags import DEFAULT_CONTEXT_SETTINGS
from snowflake.cli.api.output.types import (
    CommandResult,
    QueryJsonValueResult,
    SingleQueryResult,
)
from snowflake.cli.plugins.containers.common import print_log_lines
from snowflake.cli.plugins.containers.services.manager import ServiceManager
from snowflake.cli.plugins.object.common import tag_option, comment_option, Tag

app = typer.Typer(
    context_settings=DEFAULT_CONTEXT_SETTINGS,
    name="service",
    help="Manages Snowpark services.",
)


@app.command()
@with_output
@global_options_with_connection
def create(
        name: str = typer.Option(..., "--name", help="Job Name"),
        compute_pool: str = typer.Option(..., "--compute-pool", help="Compute Pool"),
        spec_path: Path = typer.Option(
            ...,
            "--spec-path",
            help="Spec Path",
            file_okay=True,
            dir_okay=False,
            exists=True,
        ),
        num_instances: int = typer.Option(1, "--num-instances", help="Number of instances"),
        auto_resume: bool = typer.Option(True, "--auto-resume/--no-auto-resume",
                                         help="The service will automatically resume when a service function or ingress is called."),
        external_access_integrations: Optional[List[str]] = typer.Option(None, "--eai-name",
                                                                         help="Identifies External Access Integrations(EAI) that the service can access. This option may be specified multiple times for multiple EAIs."),
        query_warehouse: Optional[str] = typer.Option(None, "--query-warehouse",
                                                      help="Warehouse to use if a service container connects to Snowflake to execute a query but does not explicitly specify a warehouse to use."),
        tags: Optional[List[Tag]] = tag_option("service"),
        comment: Optional[str] = comment_option("service"),
        **options,
) -> CommandResult:
    """
    Creates a new Snowpark Container Services service in the current schema.
    """

    cursor = ServiceManager().create(
        service_name=name,
        num_instances=num_instances,
        compute_pool=compute_pool,
        spec_path=spec_path,
        external_access_integrations=external_access_integrations,
        auto_resume=auto_resume,
        query_warehouse=query_warehouse,
        tags=tags,
        comment=comment
    )
    return SingleQueryResult(cursor)


@app.command()
@with_output
@global_options_with_connection
def status(
    name: str = typer.Argument(..., help="Name of the service."), **options
) -> CommandResult:
    """
    Retrieves status of a Snowpark Container Services service.
    """
    cursor = ServiceManager().status(service_name=name)
    return QueryJsonValueResult(cursor)


@app.command()
@global_options_with_connection
def logs(
    name: str = typer.Argument(..., help="Name of the service."),
    container_name: str = typer.Option(
        ..., "--container-name", help="Name of the container."
    ),
    instance_id: str = typer.Option(..., "--instance-id", help="Instance Id."),
    num_lines: int = typer.Option(500, "--num-lines", help="Num Lines"),
    **options,
):
    """
    Retrieves local logs from a Snowpark Container Services service container.
    """
    results = ServiceManager().logs(
        service_name=name,
        instance_id=instance_id,
        container_name=container_name,
        num_lines=num_lines,
    )
    cursor = results.fetchone()
    logs = next(iter(cursor)).split("\n")
    print_log_lines(sys.stdout, name, "0", logs)
