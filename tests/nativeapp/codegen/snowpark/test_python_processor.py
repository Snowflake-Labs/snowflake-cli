from __future__ import annotations

import copy
import subprocess
from pathlib import Path
from textwrap import dedent
from unittest import mock

import pytest
from snowflake.cli.api.project.schemas.native_app.path_mapping import ProcessorMapping
from snowflake.cli.plugins.nativeapp.codegen.sandbox import (
    ExecutionEnvironmentType,
    SandboxExecutionError,
)
from snowflake.cli.plugins.nativeapp.codegen.snowpark.python_processor import (
    SnowparkAnnotationProcessor,
    _determine_virtual_env,
    _execute_in_sandbox,
    edit_setup_script_with_exec_imm_sql,
    generate_create_sql_ddl_statement,
    generate_grant_sql_ddl_statements,
    generate_new_sql_file_name,
)

from tests.testing_utils.files_and_dirs import temp_local_dir

PROJECT_ROOT = Path("/path/to/project")

# --------------------------------------------------------
# ------------- _determine_virtual_env -------------------
# --------------------------------------------------------


@pytest.mark.parametrize(
    "input_param, expected",
    [
        [ProcessorMapping(name="dummy", properties={"random": "random"}), {}],
        [ProcessorMapping(name="dummy", properties={"env": {"random": "random"}}), {}],
        [
            ProcessorMapping(
                name="dummy",
                properties={"env": {"type": "conda", "name": "snowpark-dev"}},
            ),
            {"env_type": ExecutionEnvironmentType.CONDA, "name": "snowpark-dev"},
        ],
        [
            ProcessorMapping(
                name="dummy", properties={"env": {"type": "venv", "path": "some/path"}}
            ),
            {
                "env_type": ExecutionEnvironmentType.VENV,
                "path": PROJECT_ROOT / "some/path",
            },
        ],
        [
            ProcessorMapping(
                name="dummy", properties={"env": {"type": "venv", "path": "/some/path"}}
            ),
            {"env_type": ExecutionEnvironmentType.VENV, "path": Path("/some/path")},
        ],
        [
            ProcessorMapping(name="dummy", properties={"env": {"type": "current"}}),
            {"env_type": ExecutionEnvironmentType.CURRENT},
        ],
        [ProcessorMapping(name="dummy", properties={"env": {"type": "other"}}), {}],
        [
            ProcessorMapping(name="dummy", properties={"env": {"type": "conda"}}),
            {"env_type": ExecutionEnvironmentType.CONDA, "name": None},
        ],
        [
            ProcessorMapping(name="dummy", properties={"env": {"type": "venv"}}),
            {"env_type": ExecutionEnvironmentType.VENV, "path": None},
        ],
    ],
)
def test_determine_virtual_env(input_param, expected):
    actual = _determine_virtual_env(project_root=PROJECT_ROOT, processor=input_param)
    assert actual == expected


# --------------------------------------------------------
# --------------- _execute_in_sandbox --------------------
# --------------------------------------------------------


@mock.patch(
    "snowflake.cli.plugins.nativeapp.codegen.snowpark.python_processor.execute_script_in_sandbox"
)
def test_execute_in_sandbox_full_entity(mock_sandbox):
    mock_completed_process = mock.MagicMock(spec=subprocess.CompletedProcess)
    mock_completed_process.stdout = '[{"name": "john"}, {"name": "jane"}]'
    mock_completed_process.stderr = ""
    mock_completed_process.returncode = 0
    mock_sandbox.return_value = mock_completed_process

    entity = _execute_in_sandbox(
        py_file="some_file", deploy_root=Path("some/path"), kwargs={}
    )
    assert entity == [{"name": "john"}, {"name": "jane"}]


@mock.patch(
    "snowflake.cli.plugins.nativeapp.codegen.snowpark.python_processor.execute_script_in_sandbox"
)
def test_execute_in_sandbox_all_possible_none_cases(mock_sandbox):
    mock_completed_process = mock.MagicMock(spec=subprocess.CompletedProcess)
    mock_completed_process.returncode = 1
    mock_completed_process.stderr = "DUMMY"
    mock_completed_process.stdout = "DUMMY"
    mock_sandbox.return_value = mock_completed_process
    assert (
        _execute_in_sandbox(
            py_file="some_file", deploy_root=Path("some/path"), kwargs={}
        )
        is None
    )

    mock_completed_process.returncode = 0
    mock_completed_process.stderr = "DUMMY"
    mock_completed_process.stdout = '[{"name": "john"}, {"name": "jane"}'  # Bad input
    assert (
        _execute_in_sandbox(
            py_file="some_file", deploy_root=Path("some/path"), kwargs={}
        )
        is None
    )

    mock_sandbox.side_effect = SandboxExecutionError("dummy error")
    assert (
        _execute_in_sandbox(
            py_file="some_file", deploy_root=Path("some/path"), kwargs={}
        )
        is None
    )

    mock_sandbox.side_effect = ValueError("dummy error")
    assert (
        _execute_in_sandbox(
            py_file="some_file", deploy_root=Path("some/path"), kwargs={}
        )
        is None
    )


# --------------------------------------------------------
# ------- generate_create_sql_ddl_statement -------------
# --------------------------------------------------------


def test_generate_create_sql_ddl_statements_w_all_entries(
    native_app_extension_function, snapshot
):
    assert generate_create_sql_ddl_statement(native_app_extension_function) == snapshot


def test_generate_create_sql_ddl_statements_w_select_entries(
    native_app_extension_function, snapshot
):
    native_app_extension_function.imports = None
    native_app_extension_function.packages = None
    native_app_extension_function.schema_name = None
    native_app_extension_function.secrets = None
    native_app_extension_function.external_access_integrations = None
    assert generate_create_sql_ddl_statement(native_app_extension_function) == snapshot


# --------------------------------------------------------
# ------- generate_grant_sql_ddl_statements --------------
# --------------------------------------------------------


def test_generate_grant_sql_ddl_statements(native_app_extension_function, snapshot):
    assert generate_grant_sql_ddl_statements(native_app_extension_function) == snapshot


# --------------------------------------------------------
# --------- generate_new_sql_file_name ----------------
# --------------------------------------------------------


@pytest.mark.parametrize("py_file", ["stagepath/main.py", "stagepath/mod/add.py"])
def test_generate_new_sql_file_name(py_file):
    dir_structure = {
        "output/deploy": None,
        "output/deploy/stagepath/main.py": "# this is a file\n",
        "output/deploy/stagepath/mod/add.py": "# this is a file\n",
    }

    # With a real directory structure
    with temp_local_dir(dir_structure=dir_structure) as local_path:
        deploy_root = Path(local_path, "output", "deploy")
        generated_root = Path(deploy_root, "__generated")
        sql_file_path = generate_new_sql_file_name(
            deploy_root=deploy_root,
            generated_root=generated_root,
            py_file=Path(deploy_root, py_file),
        )
        assert sql_file_path == Path(generated_root, Path(py_file).with_suffix(".sql"))


# --------------------------------------------------------
# --------- create_and_write_to_sql_files ----------------
# --------------------------------------------------------


# def test_create_and_write_to_sql_files_no_existing_generate(snapshot):
#     dir_structure = {
#         "output/deploy/main.py": "# this is a file\n",
#         "output/deploy/moduleA/main.py": "# this is a file\n",
#         "output/deploy/moduleB/main.py": "# this is a file\n",
#     }
#     with temp_local_dir(dir_structure) as local_path:
#         deploy_root = Path(local_path, "output", "deploy")
#         dest_file_py_file_to_ddl_map: Dict[Path, Path] = {
#             Path(deploy_root, "main.py"): "  ",
#             Path(deploy_root, "moduleA", "main.py"): "some text",
#             Path(deploy_root, "moduleB", "main.py"): "some text",
#         }

#         dest_file_to_sql_files = create_and_write_to_sql_files(
#             dest_file_py_file_to_ddl_map=dest_file_py_file_to_ddl_map,
#             deploy_root=deploy_root,
#             generated_root=Path(deploy_root, "__generated"),
#         )

#         assert len(dest_file_to_sql_files) == 2
#         relative_paths_dict: Dict[Path, Path] = {}
#         absolute_deploy = resolve_without_follow(deploy_root)
#         for dest_file, sql_file in dest_file_to_sql_files.items():
#             absolute_dest = resolve_without_follow(dest_file)
#             relative_dest = absolute_dest.relative_to(absolute_deploy)
#             absolute_sql = resolve_without_follow(sql_file)
#             relative_sql = absolute_sql.relative_to(absolute_deploy)
#             relative_paths_dict[relative_dest] = relative_sql

#             with open(sql_file, "r") as f:
#                 assert f.read() == "some text"

#         assert relative_paths_dict == snapshot


# def test_create_and_write_to_sql_files_w_existing_generate(snapshot):
#     dir_structure = {
#         "output/deploy/moduleA/main.py": "# this is a file\n",
#         "output/deploy/moduleB/main.py": "# this is a file\n",
#         "output/deploy/__generated/moduleB/main.sql": "#this is a file",
#     }
#     with temp_local_dir(dir_structure) as local_path:
#         deploy_root = Path(local_path, "output", "deploy")
#         dest_file_py_file_to_ddl_map: Dict[Path, Path] = {
#             Path(deploy_root, "moduleA", "main.py"): "some text",
#             Path(deploy_root, "moduleB", "main.py"): "some text",
#         }

#         dest_file_to_sql_files = create_and_write_to_sql_files(
#             dest_file_py_file_to_ddl_map=dest_file_py_file_to_ddl_map,
#             deploy_root=deploy_root,
#             generated_root=Path(deploy_root, "__generated"),
#         )

#         assert len(dest_file_to_sql_files) == 1
#         absolute_deploy = resolve_without_follow(deploy_root)
#         for dest_file, sql_file in dest_file_to_sql_files.items():
#             absolute_dest = resolve_without_follow(dest_file)
#             relative_dest = absolute_dest.relative_to(absolute_deploy)
#             absolute_sql = resolve_without_follow(sql_file)
#             relative_sql = absolute_sql.relative_to(absolute_deploy)
#             assert relative_dest == Path("moduleA/main.py")
#             assert relative_sql == Path("__generated/moduleA/main.sql")

#             with open(sql_file, "r") as f:
#                 assert f.read() == "some text"


# --------------------------------------------------------
# --------- edit_setup_script_with_exec_imm_sql ----------
# --------------------------------------------------------


def test_edit_setup_script_with_exec_imm_sql(snapshot):
    manifest_contents = dedent(
        f"""\
        manifest_version: 1

        artifacts:
            setup_script: moduleA/moduleC/setup.sql
        """
    )
    dir_structure = {
        "output/deploy/manifest.yml": manifest_contents,
        "output/deploy/moduleA/moduleC/setup.sql": "create application role app_public;",
        "output/deploy/__generated/moduleB/dummy.sql": "#this is a file",
        "output/deploy/__generated/dummy.sql": "#this is a file",
    }

    with temp_local_dir(dir_structure=dir_structure) as local_path:
        deploy_root = Path(local_path, "output", "deploy")
        generated_root = Path(deploy_root, "__generated")
        collected_sql_files = [
            Path(generated_root, "moduleB", "dummy.sql"),
            Path(generated_root, "dummy.sql"),
        ]

        edit_setup_script_with_exec_imm_sql(
            collected_sql_files=collected_sql_files,
            deploy_root=deploy_root,
            generated_root=generated_root,
        )

        main_file = Path(deploy_root, "__generated", "__generated.sql")
        assert main_file.is_file()
        with open(main_file, "r") as f:
            assert f.read() == snapshot

        setup_file = Path(deploy_root, "moduleA", "moduleC", "setup.sql")
        with open(setup_file, "r") as f:
            assert f.read() == snapshot


def test_edit_setup_script_with_exec_imm_sql_noop(snapshot):
    manifest_contents = dedent(
        f"""\
        manifest_version: 1

        artifacts:
            setup_script: moduleA/moduleC/setup.sql
        """
    )
    dir_structure = {
        "output/deploy/manifest.yml": manifest_contents,
        "output/deploy/moduleA/moduleC/setup.sql": None,
        "output/deploy/__generated/__generated.sql": "#some text",
    }

    with temp_local_dir(dir_structure=dir_structure) as local_path:
        deploy_root = Path(local_path, "output", "deploy")
        collected_sql_files = [
            Path(deploy_root, "__generated", "dummy.sql"),
        ]
        edit_setup_script_with_exec_imm_sql(
            collected_sql_files=collected_sql_files,
            deploy_root=deploy_root,
            generated_root=Path(deploy_root, "__generated"),
        )
        main_file = Path(deploy_root, "__generated", "__generated.sql")
        assert main_file.is_file()
        with open(main_file, "r") as f:
            assert f.read() == snapshot

        dummy_file = Path(deploy_root, "__generated", "dummy.sql")
        assert not dummy_file.exists()


def test_edit_setup_script_with_exec_imm_sql_symlink(snapshot):
    manifest_contents = dedent(
        f"""\
        manifest_version: 1

        artifacts:
            setup_script: setup.sql
        """
    )
    dir_structure = {
        "setup.sql": "create application role admin;",
        "output/deploy/manifest.yml": manifest_contents,
        # "output/deploy/__generated/__generated.sql": "#some text",
    }

    with temp_local_dir(dir_structure=dir_structure) as local_path:
        deploy_root = Path(local_path, "output", "deploy")

        deploy_root_setup_script = Path(deploy_root, "setup.sql")
        deploy_root_setup_script.symlink_to(Path(local_path, "setup.sql"))

        generated_root = Path(deploy_root, "__generated")
        collected_sql_files = [
            Path(generated_root, "moduleB", "dummy.sql"),
            Path(generated_root, "dummy.sql"),
        ]
        edit_setup_script_with_exec_imm_sql(
            collected_sql_files=collected_sql_files,
            deploy_root=deploy_root,
            generated_root=Path(deploy_root, "__generated"),
        )

        main_file = Path(deploy_root, "__generated", "__generated.sql")
        assert main_file.is_file()
        with open(main_file, "r") as f:
            assert f.read() == snapshot

        # Should not be a symlink anymore
        assert not deploy_root_setup_script.is_symlink()

        with open(deploy_root_setup_script, "r") as f:
            assert f.read() == snapshot

        with open(Path(local_path, "setup.sql"), "r") as f:
            assert f.read() == snapshot


# --------------------------------------------------------
# ------------- SnowparkAnnotationProcessor --------------
# --------------------------------------------------------
manifest_contents = dedent(
    f"""\
    manifest_version: 1

    artifacts:
        setup_script: moduleA/moduleC/setup.sql
    """
)

minimal_dir_structure = {
    "a/b/c/main.py": "# this is a file\n",
    "a/b/c/data.py": "# this is a file\n",
    "output/deploy": None,
    "output/deploy/manifest.yml": manifest_contents,
    "output/deploy/moduleA/moduleC/setup.sql": "create application role app_public;",
    "output/deploy/stagepath/main.py": "# this is a file\n",
    "output/deploy/stagepath/data.py": "# this is a file\n",
    "output/deploy/stagepath/extra_import1.zip": None,
    "output/deploy/stagepath/extra_import2.zip": None,
}


@mock.patch(
    "snowflake.cli.plugins.nativeapp.codegen.snowpark.python_processor._execute_in_sandbox",
)
def test_process_no_collected_functions(
    mock_sandbox, native_app_project_instance, snapshot
):
    with temp_local_dir(minimal_dir_structure) as local_path:
        native_app_project_instance.native_app.artifacts = [
            {"src": "a/b/c/*.py", "dest": "stagepath/", "processors": ["SNOWPARK"]}
        ]
        mock_sandbox.side_effect = [None, []]
        deploy_root = Path(local_path, "output/deploy")
        generated_root = Path(deploy_root, "__generated")
        output = SnowparkAnnotationProcessor(
            project_definition=native_app_project_instance,
            project_root=local_path,
            deploy_root=deploy_root,
            generated_root=generated_root,
        ).process(
            artifact_to_process=native_app_project_instance.native_app.artifacts[0],
            processor_mapping=ProcessorMapping(name="SNOWPARK"),
            write_to_sql=False,  # For testing
        )
        assert output == snapshot
        assert not Path(generated_root, "stagepath/main.sql").exists()
        assert not Path(generated_root, "stagepath/data.sql").exists()


@mock.patch(
    "snowflake.cli.plugins.nativeapp.codegen.snowpark.python_processor._execute_in_sandbox",
)
def test_process_with_collected_functions(
    mock_sandbox,
    native_app_project_instance,
    native_app_extension_function_raw_data,
    snapshot,
):

    with temp_local_dir(minimal_dir_structure) as local_path:
        imports_variation = copy.deepcopy(native_app_extension_function_raw_data)
        imports_variation["imports"] = [
            "@dummy_stage_str",
            "/",
            "stagepath/extra_import1.zip",
            "stagepath/some_dir_str",
            "/stagepath/withslash.py",
            "stagepath/data.py",
        ]
        processor_mapping = ProcessorMapping(
            name="snowpark",
            properties={"env": {"type": "conda", "name": "snowpark-dev"}},
        )
        native_app_project_instance.native_app.artifacts = [
            {
                "src": "a/b/c/*.py",
                "dest": "stagepath/",
                "processors": [processor_mapping],
            }
        ]
        mock_sandbox.side_effect = [
            [native_app_extension_function_raw_data],
            [imports_variation],
        ]
        deploy_root = Path(local_path, "output/deploy")
        generated_root = Path(deploy_root, "__generated")
        output = SnowparkAnnotationProcessor(
            project_definition=native_app_project_instance,
            project_root=local_path,
            deploy_root=deploy_root,
            generated_root=generated_root,
        ).process(
            artifact_to_process=native_app_project_instance.native_app.artifacts[0],
            processor_mapping=processor_mapping,
        )
        # Cannot compare keys as these are temporary paths that change per test run
        # assert output == snapshot

        main_file = Path(deploy_root, "__generated", "__generated.sql")
        assert main_file.is_file()
        with open(main_file, "r") as f:
            assert f.read() == snapshot

        # Should have execute imm
        with open(
            Path(local_path, "output/deploy/moduleA/moduleC/setup.sql"), "r"
        ) as f:
            assert f.read() == snapshot

        with open(
            Path(local_path, "output/deploy/__generated/stagepath/main.sql"), "r"
        ) as f:
            assert f.read() == snapshot

        with open(
            Path(local_path, "output/deploy/__generated/stagepath/data.sql"), "r"
        ) as f:
            assert f.read() == snapshot
