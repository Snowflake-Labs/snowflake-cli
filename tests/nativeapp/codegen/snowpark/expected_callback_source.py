import functools
import sys
from typing import Any, Callable, List

try:
    import snowflake.snowpark
except ModuleNotFoundError as exc:
    print(
        "An exception occurred while importing snowflake-snowpark-python package: ",
        exc,
        file=sys.stderr,
    )
    sys.exit(1)

found_correct_version = hasattr(
    snowflake.snowpark.context, "_is_execution_environment_sandboxed_for_client"
) and hasattr(snowflake.snowpark.context, "_should_continue_registration")

if not found_correct_version:
    print(
        "Did not find the minimum required version for snowflake-snowpark-python package. Please upgrade to v1.15.0 or higher.",
        file=sys.stderr,
    )
    sys.exit(1)

orig_globals = globals().copy()

__snowflake_cli_native_app_internal_callback_return_list: List[Any] = []


def __snowflake_cli_native_app_internal_callback_replacement():
    global __snowflake_cli_native_app_internal_callback_return_list

    def __snowflake_cli_native_app_internal_transform_snowpark_object_to_json(
        extension_function_properties,
    ):

        ext_fn = extension_function_properties
        extension_function_dict = {
            "object_type": ext_fn.object_type.name,
            "object_name": ext_fn.object_name,
            "input_args": [
                {"name": input_arg.name, "datatype": type(input_arg.datatype).__name__}
                for input_arg in ext_fn.input_args
            ],
            "input_sql_types": ext_fn.input_sql_types,
            "return_sql": ext_fn.return_sql,
            "runtime_version": ext_fn.runtime_version,
            "all_imports": ext_fn.all_imports,
            "all_packages": ext_fn.all_packages,
            "handler": ext_fn.handler,
            "external_access_integrations": ext_fn.external_access_integrations,
            "secrets": ext_fn.secrets,
            "inline_python_code": ext_fn.inline_python_code,
            "raw_imports": ext_fn.raw_imports,
            "replace": ext_fn.replace,
            "if_not_exists": ext_fn.if_not_exists,
            "execute_as": ext_fn.execute_as,
            "anonymous": ext_fn.anonymous,
            # Set func based on type
            "func": ext_fn.func.__name__
            if isinstance(ext_fn.func, Callable)
            else ext_fn.func,
        }
        # Set native app params based on dictionary
        if ext_fn.native_app_params is not None:
            extension_function_dict["schema"] = ext_fn.native_app_params.get(
                "schema", None
            )
            extension_function_dict["application_roles"] = ext_fn.native_app_params.get(
                "application_roles", None
            )
        else:
            extension_function_dict["schema"] = extension_function_dict[
                "application_roles"
            ] = None
        # Imports and handler will be set at a later time.
        return extension_function_dict

    def __snowflake_cli_native_app_internal_callback_append_to_list(
        callback_return_list, extension_function_properties
    ):
        extension_function_dict = (
            __snowflake_cli_native_app_internal_transform_snowpark_object_to_json(
                extension_function_properties
            )
        )
        callback_return_list.append(extension_function_dict)
        return False

    return functools.partial(
        __snowflake_cli_native_app_internal_callback_append_to_list,
        __snowflake_cli_native_app_internal_callback_return_list,
    )


with open("dummy_file.py", mode="r", encoding="utf-8") as udf_code:
    code = udf_code.read()


snowflake.snowpark.context._is_execution_environment_sandboxed_for_client = (  # noqa: SLF001
    True
)
snowflake.snowpark.context._should_continue_registration = (  # noqa: SLF001
    __snowflake_cli_native_app_internal_callback_replacement()
)
snowflake.snowpark.session._is_execution_environment_sandboxed_for_client = (  # noqa: SLF001
    True
)

try:
    exec(code, orig_globals)
except Exception as exc:  # Catch any error
    print("An exception occurred while executing file: ", exc, file=sys.stderr)
    sys.exit(1)

print(__snowflake_cli_native_app_internal_callback_return_list)
