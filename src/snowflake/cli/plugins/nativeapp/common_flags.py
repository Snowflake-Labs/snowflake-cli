import typer
from snowflake.cli.plugins.nativeapp.utils import is_tty_interactive

InteractiveOption = typer.Option(
    is_tty_interactive(),
    "--interactive",
    "-i",
    help=f"""When enabled, this option displays prompts even if the standard input and output are not terminal devices. Defaults to True in an interactive shell environment, and False otherwise.""",
    is_flag=True,
)

ForceOption = typer.Option(
    False,
    "--force",
    help=f"""When enabled, this option causes the command to implicitly approve any prompts that arise.
    You should enable this option if interactive mode is not specified and if you want perform potentially destructive actions. Defaults to unset.""",
    is_flag=True,
)
