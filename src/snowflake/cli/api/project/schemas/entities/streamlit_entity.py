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
from __future__ import annotations

from pathlib import Path
from typing import List, Literal, Optional

from pydantic import Field
from snowflake.cli.api.project.schemas.entities.common import EntityBase
from snowflake.cli.api.project.schemas.identifier_model import ObjectIdentifierModel


class StreamlitEntity(EntityBase, ObjectIdentifierModel(object_name="Streamlit")):  # type: ignore
    type: Literal["streamlit"]  # noqa: A003
    title: Optional[str] = Field(
        title="Human-readable title for the Streamlit dashboard", default=None
    )
    query_warehouse: str = Field(
        title="Snowflake warehouse to host the app", default=None
    )
    main_file: Optional[str] = Field(
        title="Entrypoint file of the Streamlit app", default="streamlit_app.py"
    )
    pages_dir: Optional[str] = Field(title="Streamlit pages", default=None)
    stage: Optional[str] = Field(
        title="Stage in which the app’s artifacts will be stored", default="streamlit"
    )
    # Possibly can be PathMapping
    artifacts: Optional[List[Path]] = Field(
        title="List of additional files which should be included into deployment artifacts",
        default=None,
    )
