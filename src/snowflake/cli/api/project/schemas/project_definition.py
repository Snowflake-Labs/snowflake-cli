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

from typing import Any, Dict, Optional, Union

from packaging.version import Version
from pydantic import Field, field_validator
from snowflake.cli.api.project.schemas.entities.application_package import (
    ApplicationPackageEntity,
)
from snowflake.cli.api.project.schemas.native_app.native_app import NativeApp
from snowflake.cli.api.project.schemas.snowpark.snowpark import Snowpark
from snowflake.cli.api.project.schemas.streamlit.streamlit import Streamlit
from snowflake.cli.api.project.schemas.updatable_model import UpdatableModel
from snowflake.cli.api.utils.models import EnvironWithDefinedDictFallback


class _BaseDefinition(UpdatableModel):
    definition_version: Union[str, int] = Field(
        title="Version of the project definition schema, which is currently 1",
    )

    @field_validator("definition_version")
    @classmethod
    def _is_supported_version(cls, version: str) -> str:
        version = str(version)
        if version not in _version_map:
            raise ValueError(
                f'Version {version} is not supported. Supported versions: {", ".join(_version_map)}'
            )
        return version

    def meets_version_requirement(self, required_version: str) -> bool:
        return Version(self.definition_version) >= Version(required_version)


class _DefinitionV10(_BaseDefinition):
    native_app: Optional[NativeApp] = Field(
        title="Native app definitions for the project", default=None
    )
    snowpark: Optional[Snowpark] = Field(
        title="Snowpark functions and procedures definitions for the project",
        default=None,
    )
    streamlit: Optional[Streamlit] = Field(
        title="Streamlit definitions for the project", default=None
    )


class _DefinitionV11(_DefinitionV10):
    env: Optional[Dict] = Field(
        title="Environment specification for this project.",
        default=None,
        validation_alias="env",
    )

    @field_validator("env")
    @classmethod
    def _convert_env(cls, env: Optional[Dict]) -> EnvironWithDefinedDictFallback:
        variables = EnvironWithDefinedDictFallback(env if env else {})
        return variables


class _DefinitionV20(_BaseDefinition):
    entities: Dict = Field(
        title="Entity definitions.",
    )
    defaults: Optional[Dict] = Field(
        title="Default key/value entity values that are merged recursively for each entity.",
        default=None,
    )
    env: Optional[Dict] = Field(
        title="Env.",
        default=None,
    )

    @field_validator("entities")
    @classmethod
    def validate_entities(cls, entities: Dict) -> Dict:
        for key, entity in entities.items():
            entity_type = entity["entity_type"]
            if entity_type not in _entity_types_map:
                raise ValueError(f"Unsupported entity type: {entity_type}")
            entities[key] = _entity_types_map[entity_type](**entity)

        return entities


class ProjectDefinition(_DefinitionV11, _DefinitionV20):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._validate(kwargs)

    @staticmethod
    def _validate(data: Any):
        if not isinstance(data, dict):
            return
        if version := str(data.get("definition_version")):
            version_model = _version_map.get(version)
            if not version_model:
                raise ValueError(
                    f"Unknown schema version: {version}. Supported version: {_supported_version}"
                )
            version_model(**data)


_version_map = {"1": _DefinitionV10, "1.1": _DefinitionV11, "2": _DefinitionV20}
_supported_version = tuple(_version_map.keys())
_entity_types_map = {"application package": ApplicationPackageEntity}
