from urllib.parse import urlparse

from snowflake.cli.api.constants import ObjectType
from snowflake.cli.api.sql_execution import SqlExecutionMixin
from snowflake.cli.plugins.spcs.common import handle_object_already_exists
from snowflake.connector.errors import ProgrammingError


class ImageRepositoryManager(SqlExecutionMixin):
    def get_database(self):
        return self._conn.database

    def get_schema(self):
        return self._conn.schema

    def get_role(self):
        return self._conn.role

    def get_repository_url(self, repo_name: str, with_scheme: bool = True):

        repo_row = self.show_specific_object(
            "image repositories", repo_name, check_schema=True
        )
        if repo_row is None:
            raise ProgrammingError(
                f"Image repository '{self.to_fully_qualified_name(repo_name)}' does not exist or not authorized."
            )
        if with_scheme:
            return f"https://{repo_row['repository_url']}"
        else:
            return repo_row["repository_url"]

    def get_repository_api_url(self, repo_url):
        """
        Converts a repo URL to a registry OCI API URL.
        https://reg.com/db/schema/repo becomes https://reg.com/v2/db/schema/repo
        """
        parsed_url = urlparse(repo_url)

        scheme = parsed_url.scheme
        host = parsed_url.netloc
        path = parsed_url.path

        return f"{scheme}://{host}/v2{path}"

    def create(
        self,
        name: str,
        if_not_exists: bool,
        replace: bool,
    ):

        create_statement = (
            f"{'create or replace' if replace else 'create'} image repository"
        )
        if if_not_exists:
            create_statement = f"{create_statement} if not exists"
        try:
            return self._execute_schema_query(
                f"{create_statement} {name}", name=name
            )
        except ProgrammingError as e:
            handle_object_already_exists(
                e, ObjectType.IMAGE_REPOSITORY, name, replace_available=True
            )
