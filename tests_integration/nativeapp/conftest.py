from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests_integration.conftest import SnowCLIRunner


@pytest.fixture
def nativeapp_project_directory(project_directory, nativeapp_teardown):
    """Wrapper around the project_directory fixture specific to Native App testing.

    This fixture provides a context manager that does the following:
    - Automatically calls `snow app teardown` before exiting

    Parameters for the returned context manager:
    :param name: The name of the directory in tests_integration/test_data/projects to use.
    """

    @contextmanager
    def _nativeapp_project_directory(name, teardown_args: list[str] | None = None):
        with project_directory(name) as d:
            with nativeapp_teardown(project_dir=d, extra_args=teardown_args):
                yield d

    return _nativeapp_project_directory


@pytest.fixture
def nativeapp_teardown(runner: SnowCLIRunner):
    """Runs `snow app teardown` before exiting.

    This fixture provides a context manager that runs
    `snow app teardown --force --cascade` before exiting,
    regardless of any exceptions raised.

    Parameters for the returned context manager:
    :param project_dir: Path to the project directory (optional)
    :param env: Environment variables to replace os.environ (optional)
    """

    @contextmanager
    def _nativeapp_teardown(
        *,
        project_dir: Path | None = None,
        env: dict | None = None,
        extra_args: list[str] | None = None,
    ):
        try:
            yield
        finally:
            args = ["--force", "--cascade"]
            if project_dir:
                args += ["--project", str(project_dir)]
            if extra_args:
                args += extra_args
            kwargs: dict[str, Any] = {}
            if env:
                kwargs["env"] = env

            # `snow app teardown` can only teardown one package at a time for safety,
            # so when cleaning up PDFv2 tests, we need to iterate all the package entities
            # and teardown each one individually.
            snowflake_yml = (project_dir or Path.cwd()) / "snowflake.yml"
            with open(snowflake_yml, "r") as f:
                project_yml = yaml.safe_load(f)
            packages = [
                entity_id
                for entity_id, entity in project_yml.get("entities", {}).items()
                if entity["type"] == "application package"
            ]
            if packages:
                for package in packages:
                    result = runner.invoke_with_connection(
                        ["app", "teardown", *args, "--package-entity-id", package],
                        **kwargs,
                    )
                    assert result.exit_code == 0
            else:
                result = runner.invoke_with_connection(
                    ["app", "teardown", *args], **kwargs
                )
                assert result.exit_code == 0

    return _nativeapp_teardown
