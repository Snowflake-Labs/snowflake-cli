import re
import os
from typing import Optional

IDENTIFIER = r'((?:"[^"]*(?:""[^"]*)*")|(?:[A-Za-z_][\w$]{0,254}))'
DB_SCHEMA_AND_NAME = f"{IDENTIFIER}[.]{IDENTIFIER}[.]{IDENTIFIER}"
SCHEMA_AND_NAME = f"{IDENTIFIER}[.]{IDENTIFIER}"
GLOB_REGEX = r"^[a-zA-Z0-9_\-./*?**\p{L}\p{N}]+$"
RELATIVE_PATH = r"^[^/][\p{L}\p{N}_\-.][^/]*$"


def clean_identifier(input):
    """
    Removes characters that cannot be used in an unquoted identifier,
    converting to lowercase as well.
    """
    return re.sub(r"[^a-z0-9_$]", "", f"{input}".lower())


def extract_schema(qualified_name: str):
    """
    Extracts the schema from either a two-part or three-part qualified name
    (i.e. schema.object or database.schema.object). If qualified_name is not
    qualified with a schema, returns None.
    """
    if match := re.fullmatch(DB_SCHEMA_AND_NAME, qualified_name):
        return match.group(2)
    elif match := re.fullmatch(SCHEMA_AND_NAME, qualified_name):
        return match.group(1)
    return None


def generate_user_env(username: str) -> dict:
    return {
        "USER": username,
    }


def first_set_env(*keys: str):
    for k in keys:
        v = os.getenv(k)
        if v:
            return v

    return None


def get_env_username() -> Optional[str]:
    return first_set_env("USER", "USERNAME", "LOGNAME")
