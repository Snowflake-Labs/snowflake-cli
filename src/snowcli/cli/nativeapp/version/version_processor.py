import logging
from pathlib import Path
from sys import stdin, stdout
from textwrap import dedent
from typing import Dict, List, Optional

import typer
from click import ClickException
from git import Repo
from git.exc import InvalidGitRepositoryError
from rich import print
from snowcli.cli.nativeapp.artifacts import find_version_info_in_manifest_file
from snowcli.cli.nativeapp.constants import VERSION_COL
from snowcli.cli.nativeapp.exceptions import ApplicationPackageDoesNotExistError
from snowcli.cli.nativeapp.manager import (
    NativeAppCommandProcessor,
    NativeAppManager,
    ensure_correct_owner,
)
from snowcli.cli.nativeapp.run_processor import NativeAppRunProcessor
from snowcli.cli.nativeapp.utils import (
    Prompts,
    UserConfirmationPolicy,
    ask_user_confirmation,
    find_all_rows,
    find_first_row,
)
from snowcli.cli.project.util import unquote_identifier
from snowcli.exception import SnowflakeSQLExecutionError
from snowflake.connector import ProgrammingError
from snowflake.connector.cursor import DictCursor

# Custom lambdas to plug in to UserConfirmationPolicy
is_force_lambda = lambda force: force
is_interactive_mode_lambda = lambda: stdin.isatty() and stdout.isatty()
confirm_with_user_lambda = lambda prompt: typer.confirm(prompt)

log = logging.getLogger(__name__)


def check_index_changes_in_git_repo(
    project_root: Path,
    user_confirmation_policy: UserConfirmationPolicy,
) -> None:
    """
    Checks if the project root, i.e. the native apps project is a git repository. If it is a git repository,
    it also checks if there any local changes to the directory that may not be on the app package stage.
    """
    try:
        repo = Repo(project_root)

        # Check if the repo has any changes, including untracked files
        if repo.is_dirty(untracked_files=True):
            print("Changes detected in your git repository!")
            # show differences between current files and last commit
            print(repo.git.diff(repo.head.commit.tree))

            ask_user_confirmation(
                user_confirmation_policy=user_confirmation_policy,
                prompts=Prompts(
                    f"You have local changes in this repository that are not part of a previous commit. Do you still want to continue?",
                    f"Not creating a new version.",
                    "Cannot create a new version non-interactively without --force.",
                ),
            )

    except InvalidGitRepositoryError:
        pass  # not a git repository, which is acceptable


def warn_user_about_existing_release_directive(
    existing_release_directives: List[dict],
    version: str,
    package_name: str,
    user_confirmation_policy: UserConfirmationPolicy,
) -> None:
    """
    Warns the user if a version is already referenced in a release directive(s), and asks for confirmation to add a patch.
    """
    if existing_release_directives:
        release_directive_names = ", ".join(
            row["name"] for row in existing_release_directives
        )
        print(
            dedent(
                f"""\
                Version {version} already exists for application package {package_name} and in release directive(s): {release_directive_names}.
            """
            )
        )
        ask_user_confirmation(
            user_confirmation_policy=user_confirmation_policy,
            prompts=Prompts(
                f"Are you sure you want to create a new patch for version {version} of application package {package_name}? Once added, this operation cannot be undone.",
                f"Not creating a new patch.",
                "Cannot create a new patch non-interactively without --force.",
            ),
        )


class ManifestVersionNotFoundError(ClickException):
    """
    Manifest.yml file does not contain a value for the version field.
    """

    def __init__(self):
        super().__init__(self.__doc__)


class NativeAppVersionCreateProcessor(NativeAppRunProcessor):
    def __init__(self, project_definition: Dict, project_root: Path):
        super().__init__(project_definition, project_root)

    def get_existing_version_info(self, version: str) -> Optional[dict]:
        """
        Get an existing version, if present, by the same name for an application package.
        It executes a 'show versions like ... in application package' query and returns the result as single row, if one exists.
        """
        with self.use_role(self.package_role):
            show_obj_query = f"show versions like '{unquote_identifier(version)}' in application package {self.package_name}"
            show_obj_cursor = self._execute_query(
                show_obj_query, cursor_class=DictCursor
            )

            if show_obj_cursor.rowcount is None:
                raise SnowflakeSQLExecutionError(show_obj_query)

            show_obj_row = find_first_row(
                show_obj_cursor,
                lambda row: row[VERSION_COL] == unquote_identifier(version),
            )

            return show_obj_row

    def get_existing_release_directive_info_for_version(
        self, version: str
    ) -> List[dict]:
        """
        Get all existing release directives, if present, set on the version for an application package.
        It executes a 'show release directives in application package' query and returns the filtered results, if they exist.
        """
        with self.use_role(self.package_role):
            show_obj_query = (
                f"show release directives in application package {self.package_name}"
            )
            show_obj_cursor = self._execute_query(
                show_obj_query, cursor_class=DictCursor
            )

            if show_obj_cursor.rowcount is None:
                raise SnowflakeSQLExecutionError(show_obj_query)

            show_obj_rows = find_all_rows(
                show_obj_cursor,
                lambda row: row[VERSION_COL] == unquote_identifier(version),
            )

            return show_obj_rows

    def add_new_version(self, version: str) -> None:
        """
        Add a new version to an existing application package.
        """
        with self.use_role(self.package_role):
            add_version_query = dedent(
                f"""\
                    alter application package {self.package_name}
                        add version {version}
                        using @{self.stage_fqn}
                """
            )
            self._execute_query(add_version_query, cursor_class=DictCursor)
            print(
                f"Version {version} created for application package {self.package_name}."
            )

    def add_new_patch_to_version(self, version: str, patch: Optional[str]):
        """
        Add a new patch, optionally a custom one, to an existing version of an application package.
        """
        with self.use_role(self.package_role):
            add_version_query = dedent(
                f"""\
                    alter application package {self.package_name}
                        add patch {patch if patch else ""} for version {version}
                        using @{self.stage_fqn}
                """
            )
            result_cursor = self._execute_query(
                add_version_query, cursor_class=DictCursor
            )
            new_patch = result_cursor["patch"]
            print(
                f"Patch {new_patch} created for version {version} for application package {self.package_name}."
            )

    def process(
        self,
        version: Optional[str],
        patch: Optional[str],
        force: bool = False,
        *args,
        **kwargs,
    ):
        """
        Perform bundle, app package creation, stage upload, version and/or patch to an application package. If --force is provided, then no user prompts will be executed.
        """

        user_confirmation_policy = UserConfirmationPolicy(
            is_force=is_force_lambda(force),
            is_interactive_mode=is_interactive_mode_lambda(),
            confirm_with_user=confirm_with_user_lambda,
        )

        # We need build_bundle() to (optionally) find version in manifest.yml and create app package
        self.build_bundle()

        # Make sure version is not None before proceeding any further.
        # This will raise an exception if version information is not found. Patch can be None.
        if version is None:
            version, patch = find_version_info_in_manifest_file(self.deploy_root)
            if not version:
                raise ClickException(
                    "Manifest.yml file does not contain a value for the version field."
                )

        check_index_changes_in_git_repo(
            project_root=self.project_root,
            user_confirmation_policy=user_confirmation_policy,
        )

        self.create_app_package()

        with self.use_role(self.package_role):
            # Now that the application package exists, create shared data
            self._apply_package_scripts()

            # Upload files from deploy root local folder to the above stage
            self.sync_deploy_root_with_stage(self.package_role)

        # Warn if the version exists in a release directive(s)
        warn_user_about_existing_release_directive(
            existing_release_directives=self.get_existing_release_directive_info_for_version(
                version
            ),
            version=version,
            package_name=self.package_name,
            user_confirmation_policy=user_confirmation_policy,
        )

        # Add a new version to the app package
        if not self.get_existing_version_info(version):
            self.add_new_version(version=version)
            raise typer.Exit()  # A new version created automatically has patch 0, we do not need to further increment the patch.

        # Add a new patch to an existing (old) version
        self.add_new_patch_to_version(version=version, patch=patch)


class NativeAppVersionDropProcessor(NativeAppManager, NativeAppCommandProcessor):
    def __init__(self, project_definition: Dict, project_root: Path):
        super().__init__(project_definition, project_root)

    def process(self, version: Optional[str], force: bool = False, *args, **kwargs):
        """
        Drops a version associated with an application package. If --force is provided, then no user prompts will be executed.
        """
        user_confirmation_policy = UserConfirmationPolicy(
            is_force=is_force_lambda(force),
            is_interactive_mode=is_interactive_mode_lambda(),
            confirm_with_user=confirm_with_user_lambda,
        )

        # 1. Check for existing an existing application package
        show_obj_row = self.get_existing_app_pkg_info()
        if show_obj_row is None:
            raise ApplicationPackageDoesNotExistError(self.package_name)
        else:
            # Check for the right owner role
            ensure_correct_owner(
                row=show_obj_row, role=self.package_role, obj_name=self.package_name
            )

        # 2. If the user did not pass in a version string, determine from manifest.yml
        if version is None:
            log.info(
                dedent(
                    f"""\
                    Version was not provided through the CLI. Checking version in the manifest.yml instead.
                    This step will bundle your app artifacts to determine the location of the manifest.yml file.
                  """
                )
            )
            self.build_bundle()
            version, _ = find_version_info_in_manifest_file(self.deploy_root)
            if not version:
                raise ClickException(
                    "Manifest.yml file does not contain a value for the version field."
                )

        print(
            dedent(
                f"""\
                    About to drop version {version} of application package {self.package_name}.
                """
            )
        )

        # If user did not provide --force, ask for confirmation
        ask_user_confirmation(
            user_confirmation_policy=user_confirmation_policy,
            prompts=Prompts(
                f"Are you sure you want to drop version {version} of application package {self.package_name}? Once dropped, this operation cannot be undone.",
                f"Not dropping version.",
                "Cannot drop version non-interactively without --force.",
            ),
        )

        # Drop the version
        with self.use_role(self.package_role):
            try:
                self._execute_query(
                    f"alter application package {self.package_name} drop version {version}"
                )
            except ProgrammingError as err:
                raise err  # e.g. version is referenced in a release directive(s)

        print(
            f"Version {version} of application package {self.package_name} dropped successfully."
        )
