from __future__ import annotations

import logging
import os
from re import fullmatch
from pathlib import Path
from tempfile import TemporaryDirectory
from click.exceptions import ClickException
from shutil import move, rmtree
from strictyaml import load, as_document


from typing import Optional
from snowcli.cli.common.utils import generic_render_template
from snowcli.cli.project.definition_manager import DefinitionManager


log = logging.getLogger(__name__)

SNOWFLAKELABS_GITHUB_URL = "https://github.com/snowflakedb/native-apps-templates"
BASIC_TEMPLATE = "basic"

# Based on first two rules for unquoted object identifier: https://docs.snowflake.com/en/sql-reference/identifiers-syntax
PROJECT_NAME_REGEX = r"(^[a-zA-Z_])([a-zA-Z0-9_$]{0,254})"


class InitError(ClickException):
    """
    Native app project could not be initiated due to an underlying error.
    """

    def __init__(self):
        super().__init__(self.__doc__)


class ProjectNameInvalidError(ClickException):
    """
    Intended project name does not qualify as a valid identifier.
    """

    def __init__(self):
        super().__init__(self.__doc__)


class RenderingFromJinjaError(ClickException):
    """
    Could not complete rendering file from Jinja template.
    """

    def __init__(self, name: str):
        super().__init__(
            f"Could not complete rendering file from Jinja template: {name}"
        )


class CannotInitializeAnExistingProjectError(ClickException):
    """
    Cannot initialize a new project within an existing Native Application project.
    """

    def __init__(self):
        super().__init__(self.__doc__)


class DirectoryAlreadyExistsError(ClickException):
    """
    Directory already contains a project with the intended name.
    """

    name: str

    def __init__(self, name: str):
        super().__init__(
            f"This directory already contains a sub-directory called {name}. Please try a different name."
        )
        self.name = name


def is_valid_project_name(project_name: str):
    return fullmatch(PROJECT_NAME_REGEX, project_name) is not None


def render_snowflake_yml(parent_to_snowflake_yml: Path):
    """
    Create a snowflake.yml file from a jinja template at a given path.

    Args:
        parent_to_snowflake_yml (Path): The parent directory of snowflake.yml.jinja, and later snowflake.yml

    Returns:
        None
    """

    snowflake_yml_jinja = "snowflake.yml.jinja"

    try:
        generic_render_template(
            template_path=parent_to_snowflake_yml / snowflake_yml_jinja,
            data={"project_name": parent_to_snowflake_yml.name},
            output_file_path=parent_to_snowflake_yml / "snowflake.yml",
        )
        os.remove(parent_to_snowflake_yml / snowflake_yml_jinja)
    except Exception as err:
        log.error(err)
        raise RenderingFromJinjaError(snowflake_yml_jinja)


def replace_snowflake_yml_name_with_project(target_directory: Path):
    """
    Replace the native_app schema's "name" field in a snowflake.yml file with its parent directory name, i.e. the native app project, as the default start.
    This does not change the name in any other snowflake.*.yml as snowflake.yml is the base file and all others are overrides for the user to customize.

    Args:
        target_directory (str): The directory containing snowflake.yml at its root.

    Returns:
        None
    """

    path_to_snowflake_yml = target_directory / "snowflake.yml"
    contents = None

    with open(path_to_snowflake_yml) as f:
        contents = load(f.read()).data

    project_name = target_directory.name
    if (
        ("native_app" in contents)
        and ("name" in contents["native_app"])
        and (contents["native_app"]["name"] != project_name)
    ):
        contents["native_app"]["name"] = project_name
        with open(path_to_snowflake_yml, "w") as f:
            f.write(as_document(contents).as_yaml())


def validate_and_update_snowflake_yml(target_directory: Path):
    """
    Update the native_app name key in the snowflake.yml file and perform validation on the entire file.
    This step is useful when cloning from a non-Snowflake template repo which may directly have a snowflake.yml file.

    Args:
        target_directory (str): The directory containing snowflake.yml at its root.

    Returns:
        None
    """
    # 1. Determine if a snowflake.yml file exists, at the very least
    definition_manager = DefinitionManager(target_directory)

    # 2. Change the project name in snowflake.yml to project_name if not already assigned to project_name
    replace_snowflake_yml_name_with_project(target_directory=target_directory)

    # 3. Validate the Project Definition File(s)
    definition_manager.project_definition


def _init_with_url_and_no_template(
    current_working_directory: Path,
    project_name: str,
    git_url: str,
):
    """
    Initialize a Native Apps project with a git url but without any specific template specified by the user.

    Args:
        current_working_directory (str): The current working directory of the user where the project will be added.
        project_name (str): Name of the project to be created.
        git_url (str): The git URL to perform a clone from.

    Returns:
        None
    """
    from git import Repo

    target_directory: Optional[Path] = None
    try:
        # with TemporaryDirectory(dir=current_working_directory) as temp_dir:
        target_directory = current_working_directory / project_name
        target_directory.mkdir(parents=True, exist_ok=False)

        # Clone the repository with options.
        Repo.clone_from(
            url=git_url,
            to_path=target_directory,
            filter=["tree:0"],
            depth=1,
        )

        # Remove all git history
        rmtree(target_directory.joinpath(".git").resolve())

        # Non-Snowflake git URLs may have jinja files in their directory structure, but only with one variable: {{project_name}}.
        # snowCLI will throw an error during rendering if it has other variables because we do not expose a way to provide the
        # values to those variables through command line, and hence will not be able to fully render the file.
        if Path.exists(target_directory / "snowflake.yml.jinja"):
            render_snowflake_yml(parent_to_snowflake_yml=target_directory)

        # If not an official Snowflake Native App template
        if git_url != SNOWFLAKELABS_GITHUB_URL:
            validate_and_update_snowflake_yml(target_directory=target_directory)

    except Exception as err:
        # If there was any error, validation on Project Definition file or otherwise,
        # there should not be any Native Apps Project left after this.
        if target_directory:
            rmtree(target_directory.resolve())

        log.error(err)
        raise InitError()


def _init_with_url_and_template(
    current_working_directory: Path, project_name: str, git_url: str, template: str
):
    """
    Initialize a Native Apps project with a git URL and a specific template within the git URL.

    Args:
        current_working_directory (str): The current working directory of the user where the project will be added.
        project_name (str): Name of the project to be created.
        git_url (str): The git URL to perform a clone from.
        template (str): A template within the git URL to use, all other directories and files outside the template will be discarded.

    Returns:
        None
    """
    from git import Repo

    path_to_project: Optional[Path] = None
    try:
        with TemporaryDirectory(dir=current_working_directory) as temp_dir:
            # Clone the repository in the temporary directory with options.
            Repo.clone_from(
                url=git_url,
                to_path=temp_dir,
                filter=["tree:0"],
                depth=1,
            )

            # Move native-apps-basic to current_working_directory and rename to name
            move(
                src=current_working_directory / temp_dir / template,
                dst=current_working_directory / project_name,
            )

        path_to_project = current_working_directory / project_name

        if Path.exists(path_to_project / "snowflake.yml.jinja"):
            # Render snowflake.yml file from its jinja template
            render_snowflake_yml(parent_to_snowflake_yml=path_to_project)

        # If not an official Snowflake Native App template
        if git_url != SNOWFLAKELABS_GITHUB_URL:
            validate_and_update_snowflake_yml(target_directory=path_to_project)

    except Exception as err:
        # If there was any error, validation on Project Definition file or otherwise,
        # there should not be any Native Apps Project left after this.
        if path_to_project:
            rmtree(path_to_project.resolve())

        log.error(err)
        raise InitError()


def nativeapp_init(
    name: str, git_url: Optional[str] = None, template: Optional[str] = None
):
    """
    Initialize a Native Apps project in the user's current working directory, with or without the use of a template.

    Args:
        name (str): Name of the project to be created.
        git_url (str): The git URL to perform a clone from.
        template (str): A template within the git URL to use, all other directories and files outside the template will be discarded.

    Returns:
        None
    """

    current_working_directory = Path.cwd()

    # If the intended project name is not a valid identifier, fail init command
    if not is_valid_project_name(name):
        raise ProjectNameInvalidError()

    # If current directory is already contains a file named snowflake.yml, i.e. is a native apps project, fail init command.
    # We do not validate contents of the yml here though.
    path_to_snowflake_yml = current_working_directory / "snowflake.yml"
    if path_to_snowflake_yml.is_file():
        raise CannotInitializeAnExistingProjectError()

    # If a subdirectory with the same name as name exists in the current directory, fail init command
    path_to_project = current_working_directory / name
    if path_to_project.exists():
        raise DirectoryAlreadyExistsError(name)

    if (
        git_url and not template
    ):  # If user provided a git url but no template, use the full clone
        _init_with_url_and_no_template(
            current_working_directory=current_working_directory,
            project_name=name,
            git_url=git_url,
        )
    else:  # If user provided some other combination of git url and template, only prioritize the template cloning
        _init_with_url_and_template(
            current_working_directory=current_working_directory,
            project_name=name,
            git_url=git_url if git_url else SNOWFLAKELABS_GITHUB_URL,
            template=template if template else BASIC_TEMPLATE,
        )
