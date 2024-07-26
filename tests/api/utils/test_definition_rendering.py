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

import os
from textwrap import dedent
from unittest import mock

import pytest
from snowflake.cli.api.exceptions import CycleDetectedError, InvalidTemplate
from snowflake.cli.api.project.definition import load_project
from snowflake.cli.api.project.errors import SchemaValidationError
from snowflake.cli.api.utils.definition_rendering import render_definition_template
from snowflake.cli.api.utils.models import ProjectEnvironment
from snowflake.cli.api.utils.templating_functions import get_templating_functions

from tests.nativeapp.utils import NATIVEAPP_MODULE


@mock.patch.dict(os.environ, {}, clear=True)
def test_resolve_variables_in_project_no_cross_variable_dependencies():
    definition = {
        "definition_version": "1.1",
        "env": {
            "number": 1,
            "string": "foo",
            "boolean": True,
        },
    }

    result = render_definition_template(definition, {}).project_context

    assert result == {
        "fn": get_templating_functions(),
        "ctx": {
            "definition_version": "1.1",
            "env": ProjectEnvironment(
                default_env={"number": 1, "string": "foo", "boolean": True},
                override_env={},
            ),
        },
    }


@mock.patch.dict(os.environ, {}, clear=True)
def test_resolve_variables_in_project_cross_variable_dependencies():
    definition = {
        "definition_version": "1.1",
        "env": {
            "A": 42,
            "B": "b=<% ctx.env.A %>",
            "C": "<% ctx.env.B %> and <% ctx.env.A %>",
        },
    }
    result = render_definition_template(definition, {}).project_context

    assert result == {
        "fn": get_templating_functions(),
        "ctx": {
            "definition_version": "1.1",
            "env": ProjectEnvironment(
                default_env={"A": 42, "B": "b=42", "C": "b=42 and 42"}, override_env={}
            ),
        },
    }


@mock.patch.dict(os.environ, {}, clear=True)
def test_env_not_supported_in_version_1():
    definition = {
        "definition_version": "1",
        "env": {
            "A": "42",
            "B": "b=<% ctx.env.A %>",
            "C": "<% ctx.env.B %> and <% ctx.env.A %>",
        },
    }
    with pytest.raises(SchemaValidationError):
        render_definition_template(definition, {})


@mock.patch.dict(os.environ, {"A": "value"}, clear=True)
@mock.patch(f"{NATIVEAPP_MODULE}.cc.warning")
def test_no_resolve_and_warning_in_version_1(warning_mock):
    definition = {
        "definition_version": "1",
        "native_app": {"name": "test_source_<% ctx.env.A %>", "artifacts": []},
    }
    result = render_definition_template(definition, {}).project_context

    assert result == {
        "ctx": {
            "definition_version": "1",
            "native_app": {"name": "test_source_<% ctx.env.A %>", "artifacts": []},
            "env": ProjectEnvironment(default_env={}, override_env={}),
        }
    }
    warning_mock.assert_called_once_with(
        "Ignoring template pattern in project definition file. "
        "Update 'definition_version' to 1.1 or later in snowflake.yml to enable template expansion."
    )


@mock.patch.dict(os.environ, {"A": "value"}, clear=True)
@mock.patch(f"{NATIVEAPP_MODULE}.cc.warning")
def test_partial_invalid_template_in_version_1(warning_mock):
    definition = {
        "definition_version": "1",
        "native_app": {"name": "test_source_<% ctx.env.A", "artifacts": []},
    }
    result = render_definition_template(definition, {}).project_context

    assert result == {
        "ctx": {
            "definition_version": "1",
            "native_app": {"name": "test_source_<% ctx.env.A", "artifacts": []},
            "env": ProjectEnvironment(default_env={}, override_env={}),
        }
    }
    # we still want to warn if there was an incorrect attempt to use templating
    warning_mock.assert_called_once_with(
        "Ignoring template pattern in project definition file. "
        "Update 'definition_version' to 1.1 or later in snowflake.yml to enable template expansion."
    )


@mock.patch.dict(os.environ, {"A": "value"}, clear=True)
@mock.patch(f"{NATIVEAPP_MODULE}.cc.warning")
def test_no_warning_in_version_1_1(warning_mock, current_sanitized_username):
    definition = {
        "definition_version": "1.1",
        "native_app": {"name": "test_source_<% ctx.env.A %>", "artifacts": []},
    }
    result = render_definition_template(definition, {}).project_context

    assert result == {
        "fn": get_templating_functions(),
        "ctx": {
            "definition_version": "1.1",
            "native_app": {
                "name": "test_source_value",
                "artifacts": [],
                "bundle_root": "output/bundle/",
                "deploy_root": "output/deploy/",
                "generated_root": "__generated/",
                "scratch_stage": "app_src.stage_snowflake_cli_scratch",
                "source_stage": "app_src.stage",
                "package": {
                    "name": f"test_source_value_pkg_{current_sanitized_username}",
                    "distribution": "internal",
                },
                "application": {
                    "name": f"test_source_value_{current_sanitized_username}"
                },
            },
            "env": ProjectEnvironment(default_env={}, override_env={}),
        },
    }
    warning_mock.assert_not_called()


@mock.patch.dict(os.environ, {"A": "value"}, clear=True)
def test_invalid_template_in_version_1_1():
    definition = {
        "definition_version": "1.1",
        "native_app": {"name": "test_source_<% ctx.env.A", "artifacts": []},
    }
    with pytest.raises(InvalidTemplate) as err:
        render_definition_template(definition, {})

    assert err.value.message.startswith(
        "Error parsing template from project definition file. "
        "Value: 'test_source_<% ctx.env.A'. "
        "Error: unexpected end of template, expected 'end of print statement'."
    )


@mock.patch.dict(os.environ, {}, clear=True)
def test_resolve_variables_in_project_cross_project_dependencies():
    definition = {
        "definition_version": "1.1",
        "streamlit": {"name": "my_app"},
        "env": {"app": "name of streamlit is <% ctx.streamlit.name %>"},
    }
    result = render_definition_template(definition, {}).project_context
    assert result == {
        "fn": get_templating_functions(),
        "ctx": {
            "definition_version": "1.1",
            "streamlit": {
                "name": "my_app",
                "main_file": "streamlit_app.py",
                "query_warehouse": "streamlit",
                "stage": "streamlit",
            },
            "env": ProjectEnvironment(
                default_env={"app": "name of streamlit is my_app"},
                override_env={},
            ),
        },
    }


@mock.patch.dict(
    os.environ,
    {
        "lowercase": "new_lowercase_value",
        "UPPERCASE": "new_uppercase_value",
        "should_be_replaced_by_env": "test succeeded",
        "value_from_env": "this comes from os.environ",
    },
    clear=True,
)
def test_resolve_variables_in_project_environment_variables_precedence():
    definition = {
        "definition_version": "1.1",
        "env": {
            "should_be_replaced_by_env": "test failed",
            "test_variable": "<% ctx.env.lowercase %> and <% ctx.env.UPPERCASE %>",
            "test_variable_2": "<% ctx.env.value_from_env %>",
        },
    }
    result = render_definition_template(definition, {}).project_context

    assert result == {
        "fn": get_templating_functions(),
        "ctx": {
            "definition_version": "1.1",
            "env": ProjectEnvironment(
                default_env={
                    "should_be_replaced_by_env": "test failed",
                    "test_variable": "new_lowercase_value and new_uppercase_value",
                    "test_variable_2": "this comes from os.environ",
                },
                override_env={},
            ),
        },
    }
    assert result["ctx"]["env"]["lowercase"] == "new_lowercase_value"
    assert result["ctx"]["env"]["UPPERCASE"] == "new_uppercase_value"
    assert result["ctx"]["env"]["should_be_replaced_by_env"] == "test succeeded"
    assert result["ctx"]["env"]["value_from_env"] == "this comes from os.environ"


@mock.patch.dict(
    os.environ,
    {"env_var": "<% ctx.definition_version %>", "USER": "username"},
    clear=True,
)
def test_env_variables_do_not_get_resolved(current_sanitized_username):
    definition = {
        "definition_version": "1.1",
        "native_app": {"name": "test_source_<% ctx.env.env_var %>", "artifacts": []},
        "env": {
            "reference_to_name": "<% ctx.native_app.name %>",
        },
    }
    result = render_definition_template(definition, {}).project_context
    assert result == {
        "fn": get_templating_functions(),
        "ctx": {
            "definition_version": "1.1",
            "native_app": {
                "name": "test_source_<% ctx.definition_version %>",
                "artifacts": [],
                "bundle_root": "output/bundle/",
                "deploy_root": "output/deploy/",
                "generated_root": "__generated/",
                "scratch_stage": "app_src.stage_snowflake_cli_scratch",
                "source_stage": "app_src.stage",
                "package": {
                    "name": f'"test_source_<% ctx.definition_version %>_pkg_{current_sanitized_username}"',
                    "distribution": "internal",
                },
                "application": {
                    "name": f'"test_source_<% ctx.definition_version %>_{current_sanitized_username}"'
                },
            },
            "env": ProjectEnvironment(
                default_env={
                    "reference_to_name": "test_source_<% ctx.definition_version %>",
                },
                override_env={},
            ),
        },
    }

    assert result["ctx"]["env"]["env_var"] == "<% ctx.definition_version %>"


@pytest.mark.parametrize(
    "definition",
    [
        {"definition_version": "1.1", "env": {"A": "<% ctx.env.A %>"}},
        {
            "definition_version": "1.1",
            "env": {"A": "<% ctx.env.B %>", "B": "<% ctx.env.A %>"},
        },
        {
            "definition_version": "1.1",
            "env": {
                "A": "<% ctx.env.B %>",
                "B": "<% ctx.env.C %>",
                "C": "<% ctx.env.D %>",
                "D": "<% ctx.env.A %>",
            },
        },
        {
            "definition_version": "1.1",
            "native_app": {"name": "test_<% ctx.env.A %>", "artifacts": []},
            "env": {"A": "<% ctx.native_app.name %>"},
        },
        {
            "definition_version": "1.1",
            "native_app": {"name": "test_<% ctx.native_app.name %>", "artifacts": []},
        },
        {
            "definition_version": "1.1",
            "native_app": {
                "name": "test_<% ctx.native_app.source_stage %>",
                "artifacts": [],
                "source_stage": "stage <% ctx.native_app.name %>",
            },
        },
    ],
)
def test_resolve_variables_error_on_cycle(definition):
    with pytest.raises(CycleDetectedError) as err:
        render_definition_template(definition, {})

    assert err.value.message.startswith("Cycle detected in templating variable ")


@pytest.mark.parametrize(
    "definition, error_var",
    [
        (
            {
                "definition_version": "1.1",
                "native_app": {
                    "name": "app_name",
                    "artifacts": [{"src": "src/add.py", "dest": "add.py"}],
                },
                "env": {"A": "<% ctx.native_app.artifacts %>"},
            },
            "ctx.native_app.artifacts",
        ),
        (
            {
                "definition_version": "1.1",
                "native_app": {
                    "name": "app_name",
                    "artifacts": [{"src": "src/add.py", "dest": "add.py"}],
                },
                "env": {"A": "<% ctx.native_app %>"},
            },
            "ctx.native_app",
        ),
    ],
)
def test_resolve_variables_reference_non_scalar(definition, error_var):
    with pytest.raises(InvalidTemplate) as err:
        render_definition_template(definition, {})

    assert (
        err.value.message
        == f"Template variable {error_var} does not have a scalar value"
    )


@mock.patch.dict(os.environ, {"blank_env": ""}, clear=True)
def test_resolve_variables_blank_is_ok(current_sanitized_username):
    definition = {
        "definition_version": "1.1",
        "native_app": {
            "name": "<% ctx.env.blank_default_env %>",
            "deploy_root": "<% ctx.env.blank_env %>",
            "artifacts": [],
        },
        "env": {
            "blank_default_env": "",
        },
    }
    result = render_definition_template(definition, {}).project_context

    assert result == {
        "fn": get_templating_functions(),
        "ctx": {
            "definition_version": "1.1",
            "native_app": {
                "name": "",
                "deploy_root": "",
                "artifacts": [],
                "bundle_root": "output/bundle/",
                "generated_root": "__generated/",
                "scratch_stage": "app_src.stage_snowflake_cli_scratch",
                "source_stage": "app_src.stage",
                "package": {
                    "name": f"_pkg_{current_sanitized_username}",
                    "distribution": "internal",
                },
                "application": {"name": f"_{current_sanitized_username}"},
            },
            "env": ProjectEnvironment(
                default_env={
                    "blank_default_env": "",
                },
                override_env={},
            ),
        },
    }

    assert result["ctx"]["env"]["blank_env"] == ""


@pytest.mark.parametrize(
    "env, msg",
    [
        ({"app": "<% bdbdbd %>"}, "Could not find template variable bdbdbd"),
        (
            {"app": "<% ctx.streamlit.name %>"},
            "Could not find template variable ctx.streamlit.name",
        ),
        ({"app": "<% ctx.foo %>"}, "Could not find template variable ctx.foo"),
        ({"app": "<% ctx.env.get %>"}, "Could not find template variable ctx.env.get"),
        (
            {"app": "<% ctx.env.__class__ %>"},
            "Could not find template variable ctx.env.__class__",
        ),
        (
            {"app": "<% ctx.native_app.__class__ %>"},
            "Could not find template variable ctx.native_app.__class__",
        ),
        (
            {"app": "<% ctx.native_app.schema %>"},
            "Could not find template variable ctx.native_app.schema",
        ),
    ],
)
def test_resolve_variables_fails_if_referencing_unknown_variable(env, msg):
    definition = {
        "definition_version": "1.1",
        "native_app": {"name": "test_name", "artifacts": []},
        "env": env,
    }
    with pytest.raises(InvalidTemplate) as err:
        render_definition_template(definition, {})
    assert msg == err.value.message


@mock.patch.dict(os.environ, {}, clear=True)
def test_unquoted_template_usage_in_strings_yaml(named_temporary_file):
    text = """\
    definition_version: "1.1"
    env:
        value: "Snowflake is great!"
        single_line: <% ctx.env.value %>
        flow_multiline_quoted: "this is
            multiline string with template <% ctx.env.value %>"
        flow_multiline_not_quoted: this is
            multiline string with template <% ctx.env.value %>
        block_multiline: |
            this is multiline string 
            with template <% ctx.env.value %>
    """

    with named_temporary_file(suffix=".yml") as p:
        p.write_text(dedent(text))
        result = load_project([p])

    assert result.project_context.get("ctx", {}).get("env", None) == ProjectEnvironment(
        default_env={
            "block_multiline": "this is multiline string \nwith template Snowflake is great!\n",
            "flow_multiline_not_quoted": "this is multiline string with template Snowflake is great!",
            "flow_multiline_quoted": "this is multiline string with template Snowflake is great!",
            "single_line": "Snowflake is great!",
            "value": "Snowflake is great!",
        },
        override_env={},
    )


@mock.patch.dict(os.environ, {"var_with_yml": "    - app/*\n    - src\n"}, clear=True)
def test_injected_yml_in_env_should_not_be_expanded():
    definition = {
        "definition_version": "1.1",
        "env": {
            "test_env": "<% ctx.env.var_with_yml %>",
        },
    }
    result = render_definition_template(definition, {}).project_context

    assert result == {
        "fn": get_templating_functions(),
        "ctx": {
            "definition_version": "1.1",
            "env": ProjectEnvironment(
                default_env={
                    "test_env": "    - app/*\n    - src\n",
                },
                override_env={},
            ),
        },
    }

    assert result["ctx"]["env"]["var_with_yml"] == "    - app/*\n    - src\n"


@pytest.mark.parametrize(
    "template_value",
    [
        "<% ctx.env.0 %>",
        "<% ctx.env[0] %>",
        "<% ctx.0.env %>",
        "<% ctx[definition_version] %>",
    ],
)
@mock.patch.dict(os.environ, {}, clear=True)
def test_invalid_templating_syntax(template_value):
    definition = {
        "definition_version": "1.1",
        "env": {
            "test_env": template_value,
        },
    }
    with pytest.raises(InvalidTemplate) as err:
        render_definition_template(definition, {})

    assert err.value.message == f"Unexpected templating syntax in {template_value}"


def test_invalid_type_for_env_section():
    definition = {
        "definition_version": "1.1",
        "env": ["test_env", "array_val1"],
    }
    with pytest.raises(SchemaValidationError) as err:
        render_definition_template(definition, {})

    assert "Input should be a valid dictionary" in err.value.message


def test_invalid_type_for_env_variable():
    definition = {
        "definition_version": "1.1",
        "env": {
            "test_env": ["array_val1"],
        },
    }
    with pytest.raises(SchemaValidationError) as err:
        render_definition_template(definition, {})

    assert "Input should be a valid string" in err.value.message


@mock.patch.dict(os.environ, {"env_var_test": "value_from_os_env"}, clear=True)
def test_env_priority_from_cli_and_os_env_and_project_env():
    definition = {
        "definition_version": "1.1",
        "env": {
            "env_var_test": "value_from_definition_file",
            "final_value": "<% ctx.env.env_var_test %>",
        },
    }
    result = render_definition_template(
        definition, {"ctx": {"env": {"env_var_test": "value_from_cli_override"}}}
    ).project_context

    assert result == {
        "fn": get_templating_functions(),
        "ctx": {
            "definition_version": "1.1",
            "env": ProjectEnvironment(
                default_env={
                    "env_var_test": "value_from_definition_file",
                    "final_value": "value_from_cli_override",
                },
                override_env={"env_var_test": "value_from_cli_override"},
            ),
        },
    }

    assert result["ctx"]["env"]["env_var_test"] == "value_from_cli_override"


@mock.patch.dict(os.environ, {}, clear=True)
def test_values_env_from_only_overrides():
    definition = {
        "definition_version": "1.1",
        "env": {
            "final_value": "<% ctx.env.env_var_test %>",
        },
    }
    result = render_definition_template(
        definition, {"ctx": {"env": {"env_var_test": "value_from_cli_override"}}}
    ).project_context

    assert result == {
        "fn": get_templating_functions(),
        "ctx": {
            "definition_version": "1.1",
            "env": ProjectEnvironment(
                default_env={"final_value": "value_from_cli_override"},
                override_env={"env_var_test": "value_from_cli_override"},
            ),
        },
    }

    assert result["ctx"]["env"]["env_var_test"] == "value_from_cli_override"


@mock.patch.dict(os.environ, {}, clear=True)
def test_cli_env_var_blank():
    definition = {
        "definition_version": "1.1",
    }
    result = render_definition_template(
        definition, {"ctx": {"env": {"env_var_test": ""}}}
    ).project_context

    assert result == {
        "fn": get_templating_functions(),
        "ctx": {
            "definition_version": "1.1",
            "env": ProjectEnvironment(
                default_env={},
                override_env={"env_var_test": ""},
            ),
        },
    }

    assert result["ctx"]["env"]["env_var_test"] == ""


@mock.patch.dict(os.environ, {}, clear=True)
def test_cli_env_var_does_not_expand_with_templating():
    definition = {
        "definition_version": "1.1",
    }
    result = render_definition_template(
        definition, {"ctx": {"env": {"env_var_test": "<% ctx.env.something %>"}}}
    ).project_context

    assert result == {
        "fn": get_templating_functions(),
        "ctx": {
            "definition_version": "1.1",
            "env": ProjectEnvironment(
                default_env={},
                override_env={"env_var_test": "<% ctx.env.something %>"},
            ),
        },
    }

    assert result["ctx"]["env"]["env_var_test"] == "<% ctx.env.something %>"


@mock.patch.dict(os.environ, {"os_env_var": "os_env_var_value"}, clear=True)
def test_os_env_and_override_envs_in_version_1():
    definition = {
        "definition_version": "1",
    }

    override_ctx = {"ctx": {"env": {"override_env": "override_env_value"}}}
    result = render_definition_template(definition, override_ctx).project_context

    assert result == {
        "ctx": {
            "definition_version": "1",
            "env": ProjectEnvironment(
                default_env={},
                override_env={"override_env": "override_env_value"},
            ),
        }
    }

    assert result["ctx"]["env"]["override_env"] == "override_env_value"
    assert result["ctx"]["env"]["os_env_var"] == "os_env_var_value"


@mock.patch.dict(os.environ, {"debug": "true"}, clear=True)
def test_non_str_scalar_with_templates(current_sanitized_username):
    definition = {
        "definition_version": "1.1",
        "native_app": {
            "name": "test_app",
            "artifacts": [],
            "application": {"debug": "<% ctx.env.debug %>"},
        },
    }

    result = render_definition_template(definition, {}).project_context

    assert result == {
        "fn": get_templating_functions(),
        "ctx": {
            "definition_version": "1.1",
            "native_app": {
                "name": "test_app",
                "artifacts": [],
                "bundle_root": "output/bundle/",
                "deploy_root": "output/deploy/",
                "generated_root": "__generated/",
                "scratch_stage": "app_src.stage_snowflake_cli_scratch",
                "source_stage": "app_src.stage",
                "package": {
                    "name": f"test_app_pkg_{current_sanitized_username}",
                    "distribution": "internal",
                },
                "application": {
                    "name": f"test_app_{current_sanitized_username}",
                    "debug": "true",
                },
            },
            "env": ProjectEnvironment(default_env={}, override_env={}),
        },
    }


@mock.patch.dict(os.environ, {"debug": "invalid boolean"}, clear=True)
def test_non_str_scalar_with_templates_with_invalid_value():
    definition = {
        "definition_version": "1.1",
        "native_app": {
            "name": "test_app",
            "artifacts": [],
            "application": {"debug": "<% ctx.env.debug %>"},
        },
    }

    with pytest.raises(SchemaValidationError) as err:
        render_definition_template(definition, {})

    assert "Input should be a valid boolean" in err.value.message


@mock.patch.dict(os.environ, {"stage": "app_src.stage"}, clear=True)
def test_field_with_custom_validation_with_templates(current_sanitized_username):
    definition = {
        "definition_version": "1.1",
        "native_app": {
            "name": "test_app",
            "artifacts": [],
            "source_stage": "<% ctx.env.stage %>",
        },
    }

    result = render_definition_template(definition, {}).project_context

    assert result == {
        "fn": get_templating_functions(),
        "ctx": {
            "definition_version": "1.1",
            "native_app": {
                "name": "test_app",
                "artifacts": [],
                "bundle_root": "output/bundle/",
                "deploy_root": "output/deploy/",
                "generated_root": "__generated/",
                "scratch_stage": "app_src.stage_snowflake_cli_scratch",
                "source_stage": "app_src.stage",
                "package": {
                    "name": f"test_app_pkg_{current_sanitized_username}",
                    "distribution": "internal",
                },
                "application": {
                    "name": f"test_app_{current_sanitized_username}",
                },
            },
            "env": ProjectEnvironment(default_env={}, override_env={}),
        },
    }


@mock.patch.dict(os.environ, {"stage": "invalid stage name"}, clear=True)
def test_field_with_custom_validation_with_templates_and_invalid_value():
    definition = {
        "definition_version": "1.1",
        "native_app": {
            "name": "test_app",
            "artifacts": [],
            "source_stage": "<% ctx.env.stage %>",
        },
    }

    with pytest.raises(SchemaValidationError) as err:
        render_definition_template(definition, {})

    assert "Incorrect value for source_stage value of native_app" in err.value.message


@pytest.mark.parametrize(
    "na_name, app_name, pkg_name",
    [
        # valid unquoted ID
        ("safe_name", "safe_name_{user}", "safe_name_pkg_{user}"),
        # valid quoted ID with unsafe char
        ('"unsafe.name"', '"unsafe.name_{user}"', '"unsafe.name_pkg_{user}"'),
        # valid quoted ID with safe char
        ('"safe_name"', '"safe_name_{user}"', '"safe_name_pkg_{user}"'),
        # valid quoted id with double quotes char
        ('"name_""_"', '"name_""__{user}"', '"name_""__pkg_{user}"'),
        # unquoted ID with unsafe char
        ("unsafe.name", '"unsafe.name_{user}"', '"unsafe.name_pkg_{user}"'),
    ],
)
@mock.patch.dict(os.environ, {}, clear=True)
def test_defaults_native_app_pkg_name(
    na_name, app_name: str, pkg_name: str, current_sanitized_username
):
    expected_app_name = app_name.format(user=current_sanitized_username)
    expected_pkg_name = pkg_name.format(user=current_sanitized_username)

    definition = {
        "definition_version": "1.1",
        "native_app": {"name": na_name, "artifacts": []},
        "env": {
            "app_reference": "<% ctx.native_app.application.name %>",
            "pkg_reference": "<% ctx.native_app.package.name %>",
        },
    }
    result = render_definition_template(definition, {})
    project_context = result.project_context
    project_definition = result.project_definition

    assert project_definition.native_app.application.name == expected_app_name
    assert project_definition.native_app.package.name == expected_pkg_name

    env = project_context.get("ctx", {}).get("env", {})
    assert env.get("app_reference") == expected_app_name
    assert env.get("pkg_reference") == expected_pkg_name


def test_template_unknown_function():
    definition = {
        "definition_version": "1.1",
        "env": {
            "value": "<% fn.unknown_func('hello') %>",
        },
    }

    with pytest.raises(InvalidTemplate) as err:
        render_definition_template(definition, {})

    assert "Could not find template variable fn.unknown_func" in err.value.message


@pytest.mark.parametrize(
    "input_list, expected_output",
    [
        # test concatenate a constant with a variable -> quoted
        (["'first_'", "ctx.definition_version"], '"first_1.1"'),
        # test concatenate valid unquoted values  -> non-quoted
        (["'first_'", "'second'"], "first_second"),
        # test concatenate unquoted ids with unsafe chars -> quoted
        (["'first.'", "'second'"], '"first.second"'),
        # all safe chars, one with quoted id -> quoted
        (["'first_'", "'second_'", "'\"third\"'"], '"first_second_third"'),
        # one word, unsafe chars -> quoted
        (["'first.'"], '"first."'),
        # one word, safe chars -> non-quoted
        (["'first'"], "first"),
    ],
)
def test_id_concat_with_valid_values(input_list, expected_output):
    input_list_str = ", ".join(input_list)
    definition = {
        "definition_version": "1.1",
        "env": {
            "value": f"<% fn.id_concat({input_list_str}) %>",
        },
    }

    result = render_definition_template(definition, {}).project_context
    env = result.get("ctx", {}).get("env", {})
    assert env.get("value") == expected_output


def test_id_concat_with_no_args():
    definition = {
        "definition_version": "1.1",
        "env": {
            "value": f"<% fn.id_concat() %>",
        },
    }

    with pytest.raises(InvalidTemplate) as err:
        render_definition_template(definition, {})

    assert "id_concat requires at least 1 argument(s)" in err.value.message


def test_id_concat_with_non_string_arg():
    definition = {
        "definition_version": "1.1",
        "env": {
            "value": "<% fn.id_concat(123) %>",
        },
    }

    with pytest.raises(InvalidTemplate) as err:
        render_definition_template(definition, {})

    assert "id_concat only accepts String values" in err.value.message


@pytest.mark.parametrize(
    "input_val, expected_output",
    [
        # unquoted safe -> unchanged
        ("first", "first"),
        # unquoted unsafe -> unchanged
        ("first.second", "first.second"),
        # looks like quoted but invalid -> unchanged
        ('"first"second"', '"first"second"'),
        # valid quoted -> unquoted
        ('"first""second"', 'first"second'),
    ],
)
def test_id_to_str_valid_values(input_val, expected_output):
    definition = {
        "definition_version": "1.1",
        "env": {
            "value_input": input_val,
            "value_output": "<% fn.id_to_str(ctx.env.value_input) %>",
        },
    }

    result = render_definition_template(definition, {}).project_context
    env = result.get("ctx", {}).get("env", {})
    assert env.get("value_output") == expected_output


def test_id_to_str_with_no_args():
    definition = {
        "definition_version": "1.1",
        "env": {
            "value": "<% fn.id_to_str() %>",
        },
    }

    with pytest.raises(InvalidTemplate) as err:
        render_definition_template(definition, {})

    assert "id_to_str requires at least 1 argument(s)" in err.value.message


def test_id_to_str_with_two_args():
    definition = {
        "definition_version": "1.1",
        "env": {
            "value": "<% fn.id_to_str('a', 'b') %>",
        },
    }

    with pytest.raises(InvalidTemplate) as err:
        render_definition_template(definition, {})

    assert "id_to_str supports at most 1 argument(s)" in err.value.message


def test_id_to_str_with_non_string_arg():
    definition = {
        "definition_version": "1.1",
        "env": {
            "value": "<% fn.id_to_str(123) %>",
        },
    }

    with pytest.raises(InvalidTemplate) as err:
        render_definition_template(definition, {})

    assert "id_to_str only accepts String values" in err.value.message


@pytest.mark.parametrize(
    "input_val, expected_output",
    [
        # unquoted safe -> unchanged
        ("first", "first"),
        # unquoted unsafe -> quoted
        ("first.second", '"first.second"'),
        # looks like quoted but invalid -> quote it and escape
        ('"first"second"', '"""first""second"""'),
        # valid quoted -> unchanged
        ('"first""second"', '"first""second"'),
    ],
)
def test_str_to_id_valid_values(input_val, expected_output):
    definition = {
        "definition_version": "1.1",
        "env": {
            "value_input": input_val,
            "value_output": "<% fn.str_to_id(ctx.env.value_input) %>",
        },
    }

    result = render_definition_template(definition, {}).project_context
    env = result.get("ctx", {}).get("env", {})
    assert env.get("value_output") == expected_output


def test_str_to_id_with_no_args():
    definition = {
        "definition_version": "1.1",
        "env": {
            "value": "<% fn.str_to_id() %>",
        },
    }

    with pytest.raises(InvalidTemplate) as err:
        render_definition_template(definition, {})

    assert "str_to_id requires at least 1 argument(s)" in err.value.message


def test_str_to_id_with_two_args():
    definition = {
        "definition_version": "1.1",
        "env": {
            "value": "<% fn.str_to_id('a', 'b') %>",
        },
    }

    with pytest.raises(InvalidTemplate) as err:
        render_definition_template(definition, {})

    assert "str_to_id supports at most 1 argument(s)" in err.value.message


def test_str_to_id_with_non_string_arg():
    definition = {
        "definition_version": "1.1",
        "env": {
            "value": "<% fn.str_to_id(123) %>",
        },
    }

    with pytest.raises(InvalidTemplate) as err:
        render_definition_template(definition, {})

    assert "str_to_id only accepts String values" in err.value.message
