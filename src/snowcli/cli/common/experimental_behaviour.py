from snowcli.cli.common.snow_cli_global_context import global_context


def experimental_behaviour_enabled() -> bool:
    return global_context.experimental
