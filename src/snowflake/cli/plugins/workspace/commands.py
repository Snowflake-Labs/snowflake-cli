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

import typer
from snowflake.cli.api.cli_global_context import get_cli_context
from snowflake.cli.api.commands.decorators import with_project_definition
from snowflake.cli.api.commands.snow_typer import SnowTyper
from snowflake.cli.api.output.types import MessageResult
from snowflake.cli.plugins.workspace.manager import WorkspaceManager

ws = SnowTyper(
    name="ws",
    hidden=True,
    help="Deploy and interact with snowflake.yml-based entities.",
)


@ws.command(requires_connection=True)
@with_project_definition()
def validate(
    **options,
):
    """Validates the project definition file."""
    # If we get to this point, @with_project_definition() has already validated the PDF schema
    return MessageResult("Project definition is valid.")


@ws.command(requires_connection=True)
@with_project_definition()
def bundle(
    key: str = typer.Option(
        help=f"""The key of the entity you want to bundle.""",
    ),
    **options,
):
    """
    Bundles the specified entity.
    """

    cli_context = get_cli_context()
    ws = WorkspaceManager(
        project_definition=cli_context.project_definition,
        project_root=cli_context.project_root,
    )

    ws.bundle(key)
