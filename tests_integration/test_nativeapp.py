import os
import uuid

from snowflake.cli.api.project.util import generate_user_env
from snowflake.cli.api.secure_path import SecurePath
from snowflake.cli.plugins.nativeapp.init import OFFICIAL_TEMPLATES_GITHUB_URL

from tests.project.fixtures import *
from tests_integration.test_utils import (
    contains_row_with,
    not_contains_row_with,
    row_from_snowflake_session,
)

USER_NAME = f"user_{uuid.uuid4().hex}"
TEST_ENV = generate_user_env(USER_NAME)


@contextmanager
def pushd(directory: Path):
    cwd = os.getcwd()
    os.chdir(directory)
    try:
        yield directory
    finally:
        os.chdir(cwd)


# Tests a simple flow of initiating a new project, executing snow app run and teardown, all with distribution=internal
@pytest.mark.integration
def test_nativeapp_init_run_without_modifications(
    runner,
    snowflake_session,
    temporary_working_directory,
):
    project_name = "myapp"
    result = runner.invoke_json(
        ["app", "init", project_name],
        env=TEST_ENV,
    )
    assert result.exit_code == 0

    with pushd(Path(os.getcwd(), project_name)):
        result = runner.invoke_with_connection_json(
            ["app", "run"],
            env=TEST_ENV,
        )
        assert result.exit_code == 0

        try:
            # app + package exist
            package_name = f"{project_name}_pkg_{USER_NAME}".upper()
            app_name = f"{project_name}_{USER_NAME}".upper()
            assert contains_row_with(
                row_from_snowflake_session(
                    snowflake_session.execute_string(
                        f"show application packages like '{package_name}'",
                    )
                ),
                dict(name=package_name),
            )
            assert contains_row_with(
                row_from_snowflake_session(
                    snowflake_session.execute_string(
                        f"show applications like '{app_name}'",
                    )
                ),
                dict(name=app_name),
            )

            # make sure we always delete the app
            result = runner.invoke_with_connection_json(
                ["app", "teardown"],
                env=TEST_ENV,
            )
            assert result.exit_code == 0

        finally:
            # teardown is idempotent, so we can execute it again with no ill effects
            result = runner.invoke_with_connection_json(
                ["app", "teardown", "--force"],
                env=TEST_ENV,
            )
            assert result.exit_code == 0


# Tests a simple flow of an existing project, but executing snow app run and teardown, all with distribution=internal
@pytest.mark.integration
@pytest.mark.parametrize("project_definition_files", ["integration"], indirect=True)
def test_nativeapp_run_existing(
    runner,
    snowflake_session,
    project_definition_files: List[Path],
):
    project_name = "integration"
    project_dir = project_definition_files[0].parent
    with pushd(project_dir):
        result = runner.invoke_with_connection_json(
            ["app", "run"],
            env=TEST_ENV,
        )
        assert result.exit_code == 0

        try:
            # app + package exist
            package_name = f"{project_name}_pkg_{USER_NAME}".upper()
            app_name = f"{project_name}_{USER_NAME}".upper()
            assert contains_row_with(
                row_from_snowflake_session(
                    snowflake_session.execute_string(
                        f"show application packages like '{package_name}'",
                    )
                ),
                dict(name=package_name),
            )
            assert contains_row_with(
                row_from_snowflake_session(
                    snowflake_session.execute_string(
                        f"show applications like '{app_name}'"
                    )
                ),
                dict(name=app_name),
            )

            # sanity checks
            assert contains_row_with(
                row_from_snowflake_session(
                    snowflake_session.execute_string(
                        f"select count(*) from {app_name}.core.shared_view"
                    )
                ),
                {"COUNT(*)": 1},
            )
            test_string = "TEST STRING"
            assert contains_row_with(
                row_from_snowflake_session(
                    snowflake_session.execute_string(
                        f"call {app_name}.core.echo('{test_string}')"
                    )
                ),
                {"ECHO": test_string},
            )

            # make sure we always delete the app
            result = runner.invoke_with_connection_json(
                ["app", "teardown"],
                env=TEST_ENV,
            )
            assert result.exit_code == 0

        finally:
            # teardown is idempotent, so we can execute it again with no ill effects
            result = runner.invoke_with_connection_json(
                ["app", "teardown", "--force"],
                env=TEST_ENV,
            )
            assert result.exit_code == 0


# Tests a simple flow of initiating a project, executing snow app run and teardown, all with distribution=internal
@pytest.mark.integration
def test_nativeapp_init_run_handles_spaces(
    runner,
    snowflake_session,
    temporary_working_directory,
):
    project_name = "myapp"
    project_dir = "app root"
    result = runner.invoke_json(
        ["app", "init", project_dir, "--name", project_name],
        env=TEST_ENV,
    )
    assert result.exit_code == 0

    with pushd(Path(os.getcwd(), project_dir)):
        result = runner.invoke_with_connection_json(
            ["app", "run"],
            env=TEST_ENV,
        )
        assert result.exit_code == 0

        try:
            # app + package exist
            package_name = f"{project_name}_pkg_{USER_NAME}".upper()
            app_name = f"{project_name}_{USER_NAME}".upper()
            assert contains_row_with(
                row_from_snowflake_session(
                    snowflake_session.execute_string(
                        f"show application packages like '{package_name}'",
                    )
                ),
                dict(name=package_name),
            )
            assert contains_row_with(
                row_from_snowflake_session(
                    snowflake_session.execute_string(
                        f"show applications like '{app_name}'",
                    )
                ),
                dict(name=app_name),
            )

            # make sure we always delete the app
            result = runner.invoke_with_connection_json(
                ["app", "teardown"],
                env=TEST_ENV,
            )
            assert result.exit_code == 0

        finally:
            # teardown is idempotent, so we can execute it again with no ill effects
            result = runner.invoke_with_connection_json(
                ["app", "teardown", "--force"],
                env=TEST_ENV,
            )
            assert result.exit_code == 0


# Tests a simple flow of an existing project, but executing snow app run and teardown, all with distribution=external
@pytest.mark.integration
@pytest.mark.parametrize(
    "project_definition_files", ["integration_external"], indirect=True
)
def test_nativeapp_run_existing_w_external(
    runner,
    snowflake_session,
    project_definition_files: List[Path],
):
    project_name = "integration_external"
    project_dir = project_definition_files[0].parent
    with pushd(project_dir):
        result = runner.invoke_with_connection_json(
            ["app", "run"],
            env=TEST_ENV,
        )
        assert result.exit_code == 0

        try:
            # app + package exist
            package_name = f"{project_name}_pkg_{USER_NAME}".upper()
            app_name = f"{project_name}_{USER_NAME}".upper()
            assert contains_row_with(
                row_from_snowflake_session(
                    snowflake_session.execute_string(
                        f"show application packages like '{package_name}'",
                    )
                ),
                dict(name=package_name),
            )
            assert contains_row_with(
                row_from_snowflake_session(
                    snowflake_session.execute_string(
                        f"show applications like '{app_name}'"
                    )
                ),
                dict(name=app_name),
            )

            # app package contains distribution=external
            expect = row_from_snowflake_session(
                snowflake_session.execute_string(
                    f"desc application package {package_name}"
                )
            )
            assert contains_row_with(
                expect, {"property": "name", "value": package_name}
            )
            assert contains_row_with(
                expect, {"property": "distribution", "value": "EXTERNAL"}
            )

            # sanity checks
            assert contains_row_with(
                row_from_snowflake_session(
                    snowflake_session.execute_string(
                        f"select count(*) from {app_name}.core.shared_view"
                    )
                ),
                {"COUNT(*)": 1},
            )
            test_string = "TEST STRING"
            assert contains_row_with(
                row_from_snowflake_session(
                    snowflake_session.execute_string(
                        f"call {app_name}.core.echo('{test_string}')"
                    )
                ),
                {"ECHO": test_string},
            )

            # make sure we always delete the app, --force required for external distribution
            result = runner.invoke_with_connection_json(
                ["app", "teardown", "--force"],
                env=TEST_ENV,
            )
            assert result.exit_code == 0

            expect = snowflake_session.execute_string(
                f"show applications like '{app_name}'"
            )
            assert not_contains_row_with(
                row_from_snowflake_session(expect), {"name": app_name}
            )

            expect = snowflake_session.execute_string(
                f"show application packages like '{package_name}'"
            )
            assert not_contains_row_with(
                row_from_snowflake_session(expect), {"name": package_name}
            )

        finally:
            # teardown is idempotent, so we can execute it again with no ill effects
            result = runner.invoke_with_connection_json(
                ["app", "teardown", "--force"],
                env=TEST_ENV,
            )
            assert result.exit_code == 0


# Tests a simple flow of an existing project, executing snow app version create, drop and teardown, all with distribution=internal
@pytest.mark.integration
@pytest.mark.parametrize("project_definition_files", ["integration"], indirect=True)
def test_nativeapp_version_create_and_drop(
    runner,
    snowflake_session,
    project_definition_files: List[Path],
):
    project_name = "integration"
    project_dir = project_definition_files[0].parent
    with pushd(project_dir):
        result_create = runner.invoke_with_connection_json(
            ["app", "version", "create", "v1", "--force", "--skip-git-check"],
            env=TEST_ENV,
        )
        assert result_create.exit_code == 0

        try:
            # package exist
            package_name = f"{project_name}_pkg_{USER_NAME}".upper()
            assert contains_row_with(
                row_from_snowflake_session(
                    snowflake_session.execute_string(
                        f"show application packages like '{package_name}'",
                    )
                ),
                dict(name=package_name),
            )

            # app package contains version v1
            expect = snowflake_session.execute_string(
                f"show versions in application package {package_name}"
            )
            actual = runner.invoke_with_connection_json(
                ["app", "version", "list"], env=TEST_ENV
            )
            assert actual.json == row_from_snowflake_session(expect)

            result_drop = runner.invoke_with_connection_json(
                ["app", "version", "drop", "v1", "--force"],
                env=TEST_ENV,
            )
            assert result_drop.exit_code == 0
            actual = runner.invoke_with_connection_json(
                ["app", "version", "list"], env=TEST_ENV
            )
            assert len(actual.json) == 0

            # make sure we always delete the package
            result = runner.invoke_with_connection_json(
                ["app", "teardown"],
                env=TEST_ENV,
            )
            assert result.exit_code == 0

            expect = snowflake_session.execute_string(
                f"show application packages like '{package_name}'"
            )
            assert not_contains_row_with(
                row_from_snowflake_session(expect), {"name": package_name}
            )

        finally:
            # teardown is idempotent, so we can execute it again with no ill effects
            result = runner.invoke_with_connection_json(
                ["app", "teardown", "--force"],
                env=TEST_ENV,
            )
            assert result.exit_code == 0


# Tests upgrading an app from an existing loose files installation to versioned installation.
@pytest.mark.integration
@pytest.mark.parametrize("project_definition_files", ["integration"], indirect=True)
def test_nativeapp_upgrade(
    runner,
    snowflake_session,
    project_definition_files: List[Path],
):
    project_name = "integration"
    project_dir = project_definition_files[0].parent
    with pushd(project_dir):
        runner.invoke_with_connection_json(
            ["app", "run"],
            env=TEST_ENV,
        )
        runner.invoke_with_connection_json(
            ["app", "version", "create", "v1", "--force", "--skip-git-check"],
            env=TEST_ENV,
        )

        try:
            # package exist
            package_name = f"{project_name}_pkg_{USER_NAME}".upper()
            app_name = f"{project_name}_{USER_NAME}".upper()
            # app package contains version v1
            expect = snowflake_session.execute_string(
                f"show versions in application package {package_name}"
            )
            actual = runner.invoke_with_connection_json(
                ["app", "version", "list"], env=TEST_ENV
            )
            assert actual.json == row_from_snowflake_session(expect)

            runner.invoke_with_connection_json(
                ["app", "run", "--version", "v1", "--force"], env=TEST_ENV
            )

            expect = row_from_snowflake_session(
                snowflake_session.execute_string(f"desc application {app_name}")
            )
            assert contains_row_with(expect, {"property": "name", "value": app_name})
            assert contains_row_with(expect, {"property": "version", "value": "V1"})
            assert contains_row_with(expect, {"property": "patch", "value": "0"})

            runner.invoke_with_connection_json(
                ["app", "version", "drop", "v1", "--force"],
                env=TEST_ENV,
            )

            # make sure we always delete the package
            result = runner.invoke_with_connection_json(
                ["app", "teardown"],
                env=TEST_ENV,
            )
            assert result.exit_code == 0

        finally:
            # teardown is idempotent, so we can execute it again with no ill effects
            result = runner.invoke_with_connection_json(
                ["app", "teardown", "--force"],
                env=TEST_ENV,
            )
            assert result.exit_code == 0


# Tests initialization of a project from a repo with a single template
@pytest.mark.integration
def test_nativeapp_init_from_repo_with_single_template(
    runner,
    snowflake_session,
    temporary_working_directory,
):
    from git import Repo
    from git import rmtree as git_rmtree

    with SecurePath.temporary_directory() as all_templates_local_repo_path:
        # prepare a local repository with only one template (basic)
        all_templates_repo = Repo.clone_from(
            url=OFFICIAL_TEMPLATES_GITHUB_URL,
            to_path=all_templates_local_repo_path.path,
            filter=["tree:0"],
            depth=1,
        )
        all_templates_repo.close()
        git_rmtree((all_templates_local_repo_path / ".git").path)

        single_template_repo_path = all_templates_local_repo_path / "basic"
        single_template_repo = Repo.init(single_template_repo_path.path)
        single_template_repo.index.add(["**/*", "*", ".gitignore"])
        single_template_repo.index.commit("initial commit")

        # confirm that no error is thrown when initializing a project from a repo with a single template
        project_name = "myapp"
        try:
            result = runner.invoke_json(
                [
                    "app",
                    "init",
                    "--template-repo",
                    f"file://{single_template_repo_path.path}",
                    project_name,
                ],
                env=TEST_ENV,
            )
            assert result.exit_code == 0
        finally:
            single_template_repo.close()


# Tests a simple flow of executing "snow app deploy", verifying that an application package was created, and an application was not
@pytest.mark.integration
def test_nativeapp_init_deploy(
    runner,
    snowflake_session,
    temporary_working_directory,
):
    project_name = "myapp"
    result = runner.invoke_json(
        ["app", "init", project_name],
        env=TEST_ENV,
    )
    assert result.exit_code == 0

    with pushd(Path(os.getcwd(), project_name)):
        result = runner.invoke_with_connection_json(
            ["app", "deploy"],
            env=TEST_ENV,
        )
        assert result.exit_code == 0

        try:
            # package exist
            package_name = f"{project_name}_pkg_{USER_NAME}".upper()
            app_name = f"{project_name}_{USER_NAME}".upper()
            assert contains_row_with(
                row_from_snowflake_session(
                    snowflake_session.execute_string(
                        f"show application packages like '{package_name}'",
                    )
                ),
                dict(name=package_name),
            )

            # manifest file exists
            stage_name = "app_src.stage"  # as defined in native-apps-templates/basic
            stage_files = runner.invoke_with_connection_json(
                ["stage", "list-files", f"{package_name}.{stage_name}"],
                env=TEST_ENV,
            )
            assert contains_row_with(stage_files.json, {"name": "stage/manifest.yml"})

            # app does not exist
            assert not_contains_row_with(
                row_from_snowflake_session(
                    snowflake_session.execute_string(
                        f"show applications like '{app_name}'",
                    )
                ),
                dict(name=app_name),
            )

            # make sure we always delete the app
            result = runner.invoke_with_connection_json(
                ["app", "teardown"],
                env=TEST_ENV,
            )
            assert result.exit_code == 0

        finally:
            # teardown is idempotent, so we can execute it again with no ill effects
            result = runner.invoke_with_connection_json(
                ["app", "teardown", "--force"],
                env=TEST_ENV,
            )
            assert result.exit_code == 0


# Executing "snow app teardown --cascade", verifying that the application and application objects owned by the application are dropped
@pytest.mark.integration
def test_nativeapp_teardown_cascade(
    runner,
):
    pass


# Executing "snow app teardown --force --no-cascade", verifying that the application is dropped and the application objects owned by the application are not dropped
@pytest.mark.integration
def test_nativeapp_teardown_no_cascade(
    runner,
):
    pass


# Executing "snow app teardown" with owned application objects, verifying that the teardown is not executed in non-interactive mode
@pytest.mark.integration
def test_nativeapp_teardown_cascade_unset_non_interactive(
    runner,
):
    pass


# Executing "snow app teardown" with owned application objects, verifying that the user is prompted to specify cascade/no-cascade
@pytest.mark.integration
def test_nativeapp_teardown_cascade_unset_interactive(
    runner,
):
    pass
