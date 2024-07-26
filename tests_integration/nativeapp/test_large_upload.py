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

import uuid
import os
from unittest import mock

from snowflake.cli.api.project.util import generate_user_env
from snowflake.connector.constants import S3_CHUNK_SIZE
from snowflake.cli.api.secure_path import SecurePath
from snowflake.cli.api.project.definition_manager import DefinitionManager
from snowflake.cli.plugins.nativeapp.manager import NativeAppManager
from snowflake.cli.plugins.nativeapp.v2_conversions.v2_to_v1_decorator import (
    _pdf_v2_to_v1,
)
from snowflake.cli.plugins.stage.md5 import parse_multipart_md5sum

from tests.project.fixtures import *
from tests_integration.test_utils import pushd, enable_definition_v2_feature_flag

USER_NAME = f"user_{uuid.uuid4().hex}"
TEST_ENV = generate_user_env(USER_NAME)

THRESHOLD_BYTES = 100  # arbitrarily small to force chunking
TEMP_FILE_SIZE_BYTES = int(
    S3_CHUNK_SIZE * 1.6
)  # ensure our file will be uploaded multi-part


@pytest.mark.integration
@enable_definition_v2_feature_flag
@pytest.mark.parametrize(
    "project_definition_files", ["integration", "integration_v2"], indirect=True
)
def test_large_upload_skips_reupload(
    runner,
    snowflake_session,
    project_definition_files: List[Path],
):
    """
    Ensure that files uploaded in multiple parts are not re-uploaded unnecessarily.
    This test will currently fail when run on a non-AWS deployment.
    """
    project_dir = project_definition_files[0].parent
    with pushd(project_dir):

        # allows DefinitionManager to resolve the username
        from os import getenv as original_getenv

        def mock_getenv(key: str, default: str | None = None) -> str | None:
            if key.lower() == "user":
                return USER_NAME
            return original_getenv(key, default)

        # figure out what the source stage is resolved to
        with mock.patch("os.getenv", side_effect=mock_getenv):
            dm = DefinitionManager(project_dir)
            is_v1 = hasattr(dm.project_definition, "native_app")
            native_app = (
                dm.project_definition.native_app
                if is_v1
                else _pdf_v2_to_v1(dm.project_definition)
            )
            manager = NativeAppManager(native_app, project_dir)

        # deploy the application package
        result = runner.invoke_with_connection_json(
            ["app", "deploy"],
            env=TEST_ENV,
        )
        assert result.exit_code == 0

        temp_file = project_dir / "app" / "big.file"
        try:
            # generate a binary file w/random bytes and upload it in multi-part
            with SecurePath(temp_file).open("wb") as f:
                f.write(os.urandom(TEMP_FILE_SIZE_BYTES))
            snowflake_session.execute_string(
                f"put file://{temp_file} @{manager.stage_fqn}/app/ threshold={THRESHOLD_BYTES}"
            )

            # ensure that there is, in fact, a file with a multi-part md5sum
            # FIXME: this will FAIL on both Azure and GCP; find a way to only test this on AWS?
            result = runner.invoke_with_connection_json(
                ["stage", "list-files", manager.stage_fqn]
            )
            assert result.exit_code == 0
            assert isinstance(result.json, list)
            assert any(
                [parse_multipart_md5sum(row["md5"]) is not None for row in result.json]
            )

            # ensure that diff shows there is nothing to re-upload
            result = runner.invoke_with_connection_json(
                ["app", "deploy"],
                env=TEST_ENV,
            )
            assert result.exit_code == 0
            assert result.json == {
                "modified": [],
                "added": [],
                "deleted": [],
            }

        finally:
            # make sure our file has been deleted
            temp_file.unlink(missing_ok=True)

            # teardown is idempotent, so we can execute it again with no ill effects
            result = runner.invoke_with_connection_json(
                ["app", "teardown", "--force"],
                env=TEST_ENV,
            )
            assert result.exit_code == 0
