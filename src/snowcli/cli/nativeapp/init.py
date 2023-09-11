from __future__ import annotations

import logging
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from click.exceptions import ClickException
from shutil import move
from git import Repo


from typing import Optional
from snowcli.cli.project.definition import DEFAULT_USERNAME
from snowcli.cli.project.util import clean_identifier, get_env_username
from snowcli.cli.common.utils import generic_render_template

from snowcli.utils import get_client_git_version


log = logging.getLogger(__name__)

SNOWFLAKELABS_GITHUB_URL = "https://github.com/Snowflake-Labs/native-app-templates"
BASIC_TEMPLATE = "native-app-basic"


class InitError(ClickException):
    """
    Native app project could not be initiated due to an underlying error.
    """

    def __init__(self):
        super().__init__(self.__doc__)


class GitVersionIncompatibleError(ClickException):
    """
    Init requires git version to be at least 2.25.0. Please update git and try again.
    """

    def __init__(self):
        super().__init__(self.__doc__)


class GitCloneError(ClickException):
    """
    Could not complete git clone with the specified git repository URL.
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
    Directory already contains a project with the intended name
    """

    name: str

    def __init__(self, name: str):
        super().__init__(
            f"This directory already contains a sub-directory called {name}. Please try a different name."
        )
        self.name = name


def _sparse_checkout(
    git_url: str, repo_sub_directory: str, target_parent_directory: str
):
    """
    Clone the requested sub directory of a git repository from the provided git url.

    Args:
        git_url (str): The full git url to the repository to be cloned.
        repo_sub_directory (str): The sub directory name within the repository to be cloned.
        target_parent_directory (str): The parent directory where the git repository will be cloned into.

    Returns:
        None
    """

    clone_command = (
        f"git clone -n --depth=1 --filter=tree:0 {git_url} {target_parent_directory}"
    )
    sparse_checkout_command = f"""
        cd {target_parent_directory} &&
            git sparse-checkout set --no-cone {repo_sub_directory} &&
                git checkout
        """
    try:
        subprocess.run(
            clone_command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        subprocess.run(
            sparse_checkout_command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as err:
        log.error(err.stderr)
        raise GitCloneError()


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
            template_path=parent_to_snowflake_yml.joinpath(snowflake_yml_jinja),
            data={"project_name": parent_to_snowflake_yml.name},
            output_file_path=parent_to_snowflake_yml.joinpath("snowflake.yml"),
        )
        os.remove(parent_to_snowflake_yml.joinpath(snowflake_yml_jinja))
    except Exception as err:
        log.error(err)
        raise RenderingFromJinjaError(snowflake_yml_jinja)


def render_nativeapp_readme(parent_to_readme: Path, project_name: str):
    """
    Create a README.yml file from a jinja template at a given path.

    Args:
        parent_to_readme (Path): The parent directory of README.md.jinja, and later README.md

    Returns:
        None
    """

    readme_jinja = "README.md.jinja"

    default_application_name_prefix = clean_identifier(project_name)
    default_application_name_suffix = clean_identifier(
        get_env_username() or DEFAULT_USERNAME
    )

    try:
        generic_render_template(
            template_path=parent_to_readme.joinpath(readme_jinja),
            data={
                "application_name": f"{default_application_name_prefix}_{default_application_name_suffix}"
            },
            output_file_path=parent_to_readme.joinpath("README.md"),
        )
        os.remove(parent_to_readme.joinpath(readme_jinja))
    except Exception as err:
        log.error(err)
        raise RenderingFromJinjaError(readme_jinja)


def _init_without_user_provided_template(
    current_working_directory: Path, project_name: str
):
    """
    Initialize a Native Apps project without any template specified by the user.

    Args:
        current_working_directory (str): The current working directory of the user where the project will be added.
        project_name (str): Name of the project to be created.

    Returns:
        None
    """

    try:
        with TemporaryDirectory(dir=current_working_directory) as temp_dir:
            # Clone the repository in the temporary directory with options.
            Repo.clone_from(
                url=SNOWFLAKELABS_GITHUB_URL,
                to_path=temp_dir,
                filter=["tree:0"],
                depth=1,
            )

            # Move native-app-basic to current_working_directory and rename to name
            move(
                src=current_working_directory.joinpath(temp_dir, BASIC_TEMPLATE),
                dst=current_working_directory.joinpath(project_name),
            )

        # Render snowflake.yml file from its jinja template
        render_snowflake_yml(
            parent_to_snowflake_yml=current_working_directory.joinpath(project_name)
        )

        # Render README.md file from its jinja template
        render_nativeapp_readme(
            parent_to_readme=current_working_directory.joinpath(project_name, "app"),
            project_name=project_name,
        )

    except Exception as err:
        log.error(err)
        raise InitError()


def nativeapp_init(name: str, template: Optional[str] = None):
    """
    Initialize a Native Apps project in the user's local directory, with or without the use of a template.
    """

    current_working_directory = Path.cwd()

    # If current directory is already contains a file named snowflake.yml, i.e. is a native apps project, fail init command.
    # We do not validate the yml here though.
    path_to_snowflake_yml = current_working_directory.joinpath("snowflake.yml")
    if path_to_snowflake_yml.is_file():
        raise CannotInitializeAnExistingProjectError()

    # If a subdirectory with the same name as name exists in the current directory, fail init command
    path_to_project = current_working_directory.joinpath(name)
    if path_to_project.exists():
        raise DirectoryAlreadyExistsError(name)

    if template:  # If user provided a template, use the template
        # Implementation to be added as part of https://snowflakecomputing.atlassian.net/browse/SNOW-896905
        pass
    else:  # No template provided, use Native Apps Basic Template
        # The logic makes use of git sparse checkout, which was introduced in git 2.25.0. Check client's installed git version.
        # if get_client_git_version() < (2, 25):
        #     raise GitVersionIncompatibleError()
        _init_without_user_provided_template(
            current_working_directory=current_working_directory,
            project_name=name,
        )
