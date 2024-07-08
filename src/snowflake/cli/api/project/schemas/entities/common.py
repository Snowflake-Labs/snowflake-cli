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

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Generic, List, Optional, TypeVar

from pydantic import AliasChoices, Field, GetCoreSchemaHandler, ValidationInfo
from pydantic_core import core_schema
from snowflake.cli.api.project.schemas.updatable_model import (
    IdentifierField,
    UpdatableModel,
)


class EntityType(Enum):
    APPLICATION = "application"
    APPLICATION_PACKAGE = "application package"


class MetaField(UpdatableModel):
    warehouse: Optional[str] = IdentifierField(
        title="Warehouse used to run the scripts", default=None
    )
    role: Optional[str] = IdentifierField(
        title="Role to use when creating the entity object",
        default=None,
    )
    post_deploy: Optional[List[str]] = Field(
        title="List of SQL file paths relative to the project root", default=None
    )


class DefaultsField(UpdatableModel):
    schema_: Optional[str] = Field(
        title="Schema.",
        validation_alias=AliasChoices("schema"),
        default=None,
    )
    stage: Optional[str] = Field(
        title="Stage.",
        default=None,
    )


class EntityBase(ABC, UpdatableModel):
    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self.type_ = self.__class__.entity_type  # type: ignore[assignment]
        # TODO Apply defaults

    @property
    @abstractmethod
    def entity_type(self) -> EntityType:
        pass

    type_: EntityType = Field(
        title="Entity type",
        validation_alias=AliasChoices("type"),
    )

    meta: Optional[MetaField] = Field(title="Meta fields", default=None)


TargetType = TypeVar("TargetType")


class TargetField(Generic[TargetType]):
    def __init__(self, value: str):
        self.value = value

    def __repr__(self):
        return self.value

    @classmethod
    def validate(cls, value: str, info: ValidationInfo):
        return cls(value)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.with_info_after_validator_function(
            cls.validate, handler(str), field_name=handler.field_name
        )