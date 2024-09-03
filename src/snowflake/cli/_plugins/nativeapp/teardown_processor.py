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

from pathlib import Path
from textwrap import dedent
from typing import Dict, Optional

import typer
from snowflake.cli._plugins.nativeapp.constants import (
    ALLOWED_SPECIAL_COMMENTS,
    COMMENT_COL,
    OWNER_COL,
)
from snowflake.cli._plugins.nativeapp.manager import (
    NativeAppCommandProcessor,
    NativeAppManager,
)
from snowflake.cli._plugins.nativeapp.utils import (
    needs_confirmation,
)
from snowflake.cli.api.console import cli_console as cc
from snowflake.cli.api.entities.application_package_entity import (
    ApplicationPackageEntity,
)
from snowflake.cli.api.entities.utils import (
    drop_generic_object,
    ensure_correct_owner,
)
from snowflake.cli.api.errno import APPLICATION_NO_LONGER_AVAILABLE
from snowflake.connector import ProgrammingError


class NativeAppTeardownProcessor(NativeAppManager, NativeAppCommandProcessor):
    def __init__(self, project_definition: Dict, project_root: Path):
        super().__init__(project_definition, project_root)

    def drop_generic_object(
        self, object_type: str, object_name: str, role: str, cascade: bool = False
    ):
        return drop_generic_object(
            console=cc,
            object_type=object_type,
            object_name=object_name,
            role=role,
            cascade=cascade,
        )

    def drop_application(
        self, auto_yes: bool, interactive: bool = False, cascade: Optional[bool] = None
    ):
        """
        Attempts to drop the application object if all validations and user prompts allow so.
        """

        needs_confirm = True

        # 1. If existing application is not found, exit gracefully
        show_obj_row = self.get_existing_app_info()
        if show_obj_row is None:
            cc.warning(
                f"Role {self.app_role} does not own any application object with the name {self.app_name}, or the application object does not exist."
            )
            return

        # 2. Check for the right owner
        ensure_correct_owner(
            row=show_obj_row, role=self.app_role, obj_name=self.app_name
        )

        # 3. Check if created by the Snowflake CLI
        row_comment = show_obj_row[COMMENT_COL]
        if row_comment not in ALLOWED_SPECIAL_COMMENTS and needs_confirmation(
            needs_confirm, auto_yes
        ):
            should_drop_object = typer.confirm(
                dedent(
                    f"""\
                        Application object {self.app_name} was not created by Snowflake CLI.
                        Application object details:
                        Name: {self.app_name}
                        Created on: {show_obj_row["created_on"]}
                        Source: {show_obj_row["source"]}
                        Owner: {show_obj_row[OWNER_COL]}
                        Comment: {show_obj_row[COMMENT_COL]}
                        Version: {show_obj_row["version"]}
                        Patch: {show_obj_row["patch"]}
                        Are you sure you want to drop it?
                    """
                )
            )
            if not should_drop_object:
                cc.message(f"Did not drop application object {self.app_name}.")
                # The user desires to keep the app, therefore we can't proceed since it would
                # leave behind an orphan app when we get to dropping the package
                raise typer.Abort()

        # 4. Check for application objects owned by the application
        # This query will fail if the application package has already been dropped, so handle this case gracefully
        has_objects_to_drop = False
        message_prefix = ""
        cascade_true_message = ""
        cascade_false_message = ""
        interactive_prompt = ""
        non_interactive_abort = ""
        try:
            if application_objects := self.get_objects_owned_by_application():
                has_objects_to_drop = True
                message_prefix = (
                    f"The following objects are owned by application {self.app_name}"
                )
                cascade_true_message = f"{message_prefix} and will be dropped:"
                cascade_false_message = f"{message_prefix} and will NOT be dropped:"
                interactive_prompt = "Would you like to drop these objects in addition to the application? [y/n/ABORT]"
                non_interactive_abort = "Re-run teardown again with --cascade or --no-cascade to specify whether these objects should be dropped along with the application"
        except ProgrammingError as e:
            if e.errno != APPLICATION_NO_LONGER_AVAILABLE:
                raise
            application_objects = []
            message_prefix = f"Could not determine which objects are owned by application {self.app_name}"
            has_objects_to_drop = True  # potentially, but we don't know what they are
            cascade_true_message = (
                f"{message_prefix}, an unknown number of objects will be dropped."
            )
            cascade_false_message = f"{message_prefix}, they will NOT be dropped."
            interactive_prompt = f"Would you like to drop an unknown set of objects in addition to the application? [y/n/ABORT]"
            non_interactive_abort = f"Re-run teardown again with --cascade or --no-cascade to specify whether any objects should be dropped along with the application."

        if has_objects_to_drop:
            if cascade is True:
                # If the user explicitly passed the --cascade flag
                cc.message(cascade_true_message)
                with cc.indented():
                    for obj in application_objects:
                        cc.message(self._application_object_to_str(obj))
            elif cascade is False:
                # If the user explicitly passed the --no-cascade flag
                cc.message(cascade_false_message)
                with cc.indented():
                    for obj in application_objects:
                        cc.message(self._application_object_to_str(obj))
            elif interactive:
                # If the user didn't pass any cascade flag and the session is interactive
                cc.message(message_prefix)
                with cc.indented():
                    for obj in application_objects:
                        cc.message(self._application_object_to_str(obj))
                user_response = typer.prompt(
                    interactive_prompt,
                    show_default=False,
                    default="ABORT",
                ).lower()
                if user_response in ["y", "yes"]:
                    cascade = True
                elif user_response in ["n", "no"]:
                    cascade = False
                else:
                    raise typer.Abort()
            else:
                # Else abort since we don't know what to do and can't ask the user
                cc.message(message_prefix)
                with cc.indented():
                    for obj in application_objects:
                        cc.message(self._application_object_to_str(obj))
                cc.message(non_interactive_abort)
                raise typer.Abort()
        elif cascade is None:
            # If there's nothing to drop, set cascade to an explicit False value
            cascade = False

        # 5. All validations have passed, drop object
        self.drop_generic_object(
            object_type="application",
            object_name=self.app_name,
            role=self.app_role,
            cascade=cascade,
        )
        return  # The application object was successfully dropped, therefore exit gracefully

    def drop_package(self, auto_yes: bool):
        return ApplicationPackageEntity.drop(
            console=cc,
            package_name=self.package_name,
            package_role=self.package_role,
            force_drop=auto_yes,
        )

    def process(
        self,
        interactive: bool,
        force_drop: bool = False,
        cascade: Optional[bool] = None,
        *args,
        **kwargs,
    ):

        # Drop the application object
        self.drop_application(
            auto_yes=force_drop, interactive=interactive, cascade=cascade
        )

        # Drop the application package
        self.drop_package(auto_yes=force_drop)
