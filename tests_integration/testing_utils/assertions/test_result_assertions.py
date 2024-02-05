import json
from typing import Dict, List, Union

from tests_integration.conftest import CommandResult
from tests_integration.test_utils import contains_row_with


def assert_that_result_is_successful(result: CommandResult) -> None:
    assert result.exit_code == 0, result.output


def assert_that_result_is_error(result: CommandResult, expected_exit_code: int) -> None:
    assert result.exit_code == expected_exit_code, result.output


def assert_that_result_is_successful_and_output_json_contains(
    result: CommandResult,
    expected_output: Dict,
) -> None:
    assert_that_result_is_successful(result)
    assert_that_result_contains_row_with(result, expected_output)


def assert_that_result_is_successful_and_output_json_equals(
    result: CommandResult,
    expected_output: Union[Dict, List],
) -> None:
    assert_that_result_is_successful(result)
    assert result.json == expected_output


def assert_that_result_contains_row_with(result: CommandResult, expect: Dict) -> None:
    assert result.json is not None
    assert contains_row_with(result.json, expect)  # type: ignore


def assert_that_result_is_successful_and_done_is_on_output(
    result: CommandResult,
) -> None:
    assert_that_result_is_successful(result)
    assert result.output is not None
    assert json.loads(result.output) == {"message": "Done"}


def assert_that_result_is_successful_and_executed_successfully(
    result: CommandResult,
) -> None:
    """
    Checks that the command result is in the form {"status": "Statement executed successfully"}
    """
    complete_success = {"status": "Statement executed successfully."}
    assert_that_result_is_successful(result)
    if result.json is not None:
        if isinstance(result.json, dict):
            assert result.json == complete_success
        else:
            assert len(result.json) == 1
            assert result.json[0] == complete_success
    else:
        assert result.output is not None
        assert "status" in result.output
        assert "Statement executed successfully" in result.output
