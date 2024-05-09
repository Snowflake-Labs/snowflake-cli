import subprocess
from pathlib import Path
from unittest import mock

import pytest
from snowflake.cli.api.project.schemas.native_app.path_mapping import Processor
from snowflake.cli.plugins.nativeapp.codegen.artifact_processor import (
    MissingProjectDefinitionPropertyError,
)
from snowflake.cli.plugins.nativeapp.codegen.sandbox import (
    ExecutionEnvironmentType,
    SandboxExecutionError,
)
from snowflake.cli.plugins.nativeapp.codegen.snowpark.python_processor import (
    SnowparkAnnotationProcessor,
    _determine_virtual_env,
    _execute_in_sandbox,
)

from tests.testing_utils.files_and_dirs import temp_local_dir


@pytest.mark.parametrize(
    "input_param, expected",
    [
        (Processor(name="dummy", properties={"random": "random"}), {}),
        (Processor(name="dummy", properties={"env": {"random": "random"}}), {}),
        (
            Processor(
                name="dummy",
                properties={"env": {"type": "conda", "name": "snowpark-dev"}},
            ),
            {"env_type": ExecutionEnvironmentType.CONDA, "name": "snowpark-dev"},
        ),
        (
            Processor(
                name="dummy", properties={"env": {"type": "venv", "path": "some/path"}}
            ),
            {"env_type": ExecutionEnvironmentType.VENV, "path": "some/path"},
        ),
        (
            Processor(name="dummy", properties={"env": {"type": "current"}}),
            {"env_type": ExecutionEnvironmentType.CURRENT},
        ),
        (Processor(name="dummy", properties={"env": {"type": "other"}}), {}),
    ],
)
def test_determine_virtual_env(input_param, expected):
    actual = _determine_virtual_env(processor=input_param)
    assert actual == expected


@pytest.mark.parametrize(
    "input_param",
    [
        Processor(name="dummy", properties={"env": {"type": "conda"}}),
        Processor(name="dummy", properties={"env": {"type": "venv"}}),
    ],
)
def test_determine_virtual_env_exception(input_param):
    with pytest.raises(MissingProjectDefinitionPropertyError):
        _determine_virtual_env(processor=input_param)


def test_get_src_py_file_to_dest_py_file_map_case1(native_app_project_instance):
    dir_structure = {
        "a/b/c/main.py": "# this is a file\n",
        "a/b/c/d/main.py": "# this is a file\n",
        "a/b/c/main.txt": "# this is a file\n",
        "a/b/c/d/main.txt": "# this is a file\n",
        "a/b/main.py": "# this is a file\n",
        "a/b/main.txt": "# this is a file\n",
        "output/deploy": None,
        "output/deploy/stagepath/main.py": "# this is a file\n",
        "output/deploy/stagepath/d/main.py": "# this is a file\n",
    }
    with temp_local_dir(dir_structure) as local_path:
        native_app_project_instance.native_app.artifacts = [
            {"dest": "stagepath/", "src": "a/b/c/*.py", "processors": ["SNOWPARK"]}
        ]
        artifact_to_process = native_app_project_instance.native_app.artifacts[0]
        result_1 = SnowparkAnnotationProcessor(
            project_definition=native_app_project_instance,
            project_root=local_path,
            deploy_root=Path(local_path, "output/deploy"),
            processor="SNOWPARK",
            artifact_to_process=artifact_to_process,
        ).get_src_py_file_to_dest_py_file_map()
        assert len(result_1) == 1

        native_app_project_instance.native_app.artifacts = [
            {"dest": "stagepath/", "src": "a/b/c/**/*.py", "processors": ["SNOWPARK"]}
        ]
        artifact_to_process = native_app_project_instance.native_app.artifacts[0]
        result_2 = SnowparkAnnotationProcessor(
            project_definition=native_app_project_instance,
            project_root=local_path,
            deploy_root=Path(local_path, "output/deploy"),
            processor="SNOWPARK",
            artifact_to_process=artifact_to_process,
        ).get_src_py_file_to_dest_py_file_map()
        assert len(result_2) == 2


def test_get_src_py_file_to_dest_py_file_map_case1_fails(native_app_project_instance):
    dir_structure = {
        "a/b/c/main.py": "# this is a file\n",
        "a/b/c/d/main.py": "# this is a file\n",
        "output/deploy": None,
    }
    with temp_local_dir(dir_structure) as local_path:
        native_app_project_instance.native_app.artifacts = [
            {"dest": "stagepath/", "src": "a/b/c/*.py", "processors": ["SNOWPARK"]}
        ]
        artifact_to_process = native_app_project_instance.native_app.artifacts[0]
        result_1 = SnowparkAnnotationProcessor(
            project_definition=native_app_project_instance,
            project_root=local_path,
            deploy_root=Path(local_path, "output/deploy"),
            processor="SNOWPARK",
            artifact_to_process=artifact_to_process,
        ).get_src_py_file_to_dest_py_file_map()
        assert len(result_1) == 0


@pytest.mark.parametrize(
    "custom_artifacts",
    [
        [{"dest": "stagepath/", "src": "a/b/c/**/*", "processors": ["SNOWPARK"]}],
        [{"dest": "stagepath/", "src": "a/b/c/*", "processors": ["SNOWPARK"]}],
    ],
)
def test_get_src_py_file_to_dest_py_file_map_case2_case3(
    custom_artifacts, native_app_project_instance
):
    dir_structure = {
        "a/b/c/main.py": "# this is a file\n",
        "a/b/c/d/main.py": "# this is a file\n",
        "a/b/c/main.txt": "# this is a file\n",
        "a/b/c/d/main.txt": "# this is a file\n",
        "a/b/main.py": "# this is a file\n",
        "a/b/main.txt": "# this is a file\n",
        "output/deploy": None,
        "output/deploy/stagepath/main.py": "# this is a file\n",
        "output/deploy/stagepath/d/main.py": "# this is a file\n",
        "output/deploy/stagepath/main.txt": "# this is a file\n",
        "output/deploy/stagepath/d/main.txt": "# this is a file\n",
    }
    with temp_local_dir(dir_structure) as local_path:
        native_app_project_instance.native_app.artifacts = custom_artifacts
        artifact_to_process = native_app_project_instance.native_app.artifacts[0]
        result_1 = SnowparkAnnotationProcessor(
            project_definition=native_app_project_instance,
            project_root=local_path,
            deploy_root=Path(local_path, "output/deploy"),
            processor="SNOWPARK",
            artifact_to_process=artifact_to_process,
        ).get_src_py_file_to_dest_py_file_map()
        assert len(result_1) == 2


def test_get_src_py_file_to_dest_py_file_map_case4(native_app_project_instance):
    dir_structure = {
        "a/b/c/d/main.py": "# this is a file\n",
        "output/deploy": None,
        "output/deploy/stagepath/stagemain.py": "# this is a file\n",
    }
    with temp_local_dir(dir_structure) as local_path:
        native_app_project_instance.native_app.artifacts = [
            {
                "dest": "stagepath/stagemain.py",
                "src": "a/b/c/d/main.py",
                "processors": ["SNOWPARK"],
            }
        ]
        artifact_to_process = native_app_project_instance.native_app.artifacts[0]
        result_1 = SnowparkAnnotationProcessor(
            project_definition=native_app_project_instance,
            project_root=local_path,
            deploy_root=Path(local_path, "output/deploy"),
            processor="SNOWPARK",
            artifact_to_process=artifact_to_process,
        ).get_src_py_file_to_dest_py_file_map()
        assert len(result_1) == 1


@mock.patch(
    "snowflake.cli.plugins.nativeapp.codegen.snowpark.python_processor._execute_in_sandbox",
    side_effect=ValueError(),
)
def test_process_exception(mock_sandbox, native_app_project_instance):
    dir_structure = {
        "a/b/c/main.py": "# this is a file\n",
        "a/b/c/d/main.py": "# this is a file\n",
        "a/b/c/main.txt": "# this is a file\n",
        "a/b/c/d/main.txt": "# this is a file\n",
        "a/b/main.py": "# this is a file\n",
        "a/b/main.txt": "# this is a file\n",
        "output/deploy": None,
        "output/deploy/stagepath/main.py": "# this is a file\n",
    }
    with temp_local_dir(dir_structure) as local_path:
        native_app_project_instance.native_app.artifacts = [
            {"dest": "stagepath/", "src": "a/b/c/*.py", "processors": ["SNOWPARK"]}
        ]
        artifact_to_process = native_app_project_instance.native_app.artifacts[0]
        result_1 = SnowparkAnnotationProcessor(
            project_definition=native_app_project_instance,
            project_root=local_path,
            deploy_root=Path(local_path, "output/deploy"),
            processor="SNOWPARK",
            artifact_to_process=artifact_to_process,
        ).process()
        assert len(result_1) == 1
        assert list(result_1.values())[0] is None


@mock.patch(
    "snowflake.cli.plugins.nativeapp.codegen.snowpark.python_processor.execute_script_in_sandbox",
    side_effect=SandboxExecutionError("some_err"),
)
@mock.patch(
    "snowflake.cli.plugins.nativeapp.codegen.snowpark.python_processor.jinja_render_from_file",
    return_value="some_src",
)
def test_execute_in_sandbox_none_entity(mock_jinja, mock_sandbox):
    entity = _execute_in_sandbox(
        py_file="some_file", deploy_root=Path("some/path"), kwargs={}
    )
    assert entity is None


@mock.patch(
    "snowflake.cli.plugins.nativeapp.codegen.snowpark.python_processor.execute_script_in_sandbox"
)
@mock.patch(
    "snowflake.cli.plugins.nativeapp.codegen.snowpark.python_processor.jinja_render_from_file",
    return_value="some_src",
)
def test_execute_in_sandbox_full_entity(mock_jinja, mock_sandbox):
    mock_completed_process = mock.MagicMock(spec=subprocess.CompletedProcess)
    mock_completed_process.stdout = '[{"name": "john"}, {"name": "jane"}]'
    mock_sandbox.return_value = mock_completed_process

    entity = _execute_in_sandbox(
        py_file="some_file", deploy_root=Path("some/path"), kwargs={}
    )
    assert len(entity) == 2
