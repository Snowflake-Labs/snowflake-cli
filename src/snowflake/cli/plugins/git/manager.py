from pathlib import Path
from textwrap import dedent
from typing import List, Optional

from snowflake.cli.api.commands.flags import OnErrorType
from snowflake.cli.plugins.object.stage.manager import StageManager
from snowflake.connector.cursor import SnowflakeCursor


class GitManager(StageManager):
    def show_branches(self, repo_name: str, like: str) -> SnowflakeCursor:
        return self._execute_query(f"show git branches like '{like}' in {repo_name}")

    def show_tags(self, repo_name: str, like: str) -> SnowflakeCursor:
        return self._execute_query(f"show git tags like '{like}' in {repo_name}")

    def fetch(self, repo_name: str) -> SnowflakeCursor:
        return self._execute_query(f"alter git repository {repo_name} fetch")

    def create(
        self, repo_name: str, api_integration: str, url: str, secret: str
    ) -> SnowflakeCursor:
        query = dedent(
            f"""
            create git repository {repo_name}
            api_integration = {api_integration}
            origin = '{url}'
            """
        )
        if secret is not None:
            query += f"git_credentials = {secret}\n"
        return self._execute_query(query)

    def execute(
        self,
        repository_path: str,
        on_error: OnErrorType,
        variables: Optional[List[str]] = None,
    ):
        return super().execute(
            stage_path=repository_path, on_error=on_error, variables=variables
        )

    @staticmethod
    def get_stage_name_from_path(path: str, is_git_repository: bool = False):
        """
        Returns stage name from potential path on stage. For example
        repo/branches/main/foo/bar -> repo/branches/main/
        """
        return f"{'/'.join(Path(path).parts[0:3])}/"
