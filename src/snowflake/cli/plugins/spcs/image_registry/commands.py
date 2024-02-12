from click import ClickException
from snowflake.cli.api.commands.snow_typer import SnowTyper
from snowflake.cli.api.output.types import MessageResult, ObjectResult
from snowflake.cli.plugins.spcs.image_registry.manager import (
    NoImageRepositoriesFoundError,
    RegistryManager,
)

app = SnowTyper(
    name="image-registry",
    help="Manages Snowpark registries.",
)


@app.command("token", requires_connection=True)
def token(**options) -> ObjectResult:
    """
    Gets the token from environment to use for authenticating with the registry. Note that this token is specific
    to your current user and will not grant access to any repositories that your current user cannot access.
    """
    return ObjectResult(RegistryManager().get_token())


@app.command(requires_connection=True)
def url(**options) -> MessageResult:
    """
    Gets the image registry URL for the current account. Must be called from a
    role that can view at least one image repository in the image registry.
    """
    try:
        return MessageResult(RegistryManager().get_registry_url())
    except NoImageRepositoriesFoundError:
        raise ClickException(
            "No image repository found. To get the registry url, please switch to a role with read access to at least one image repository or create a new image repository first."
        )
