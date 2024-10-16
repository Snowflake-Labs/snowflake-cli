from __future__ import annotations

import re
from typing import List, Optional, Union

from pydantic import Field, field_validator
from snowflake.cli.api.project.schemas.updatable_model import UpdatableModel
from snowflake.cli.api.project.schemas.v1.native_app.path_mapping import PathMapping
from snowflake.cli.api.project.util import (
    DB_SCHEMA_AND_NAME,
)


class Service(UpdatableModel):
    name: str = Field(
        title="Project identifier",
    )
    source_stage: str = Field(
        title="Identifier of the stage that stores service source code.",
    )
    spec: str = Field(
        title="Service spec file path",
    )
    source_repo: str = Field(
        title="Identifier of the image repo that stores image source code.",
    )
    images: List[Union[PathMapping, str]] = Field(
        title="List of image source and destination pairs to add to the deploy root",
    )
    compute_pool: str = Field(
        title="Compute pool where the service will be deployed.",
    )
    min_instances: int = Field(
        title="Service min instances",
    )
    max_instances: int = Field(
        title="Service max instances",
    )
    query_warehouse: Optional[str] = Field(
        title="Default warehouse to run queries in the service.",
    )
    comment: Optional[str] = Field(
        title="Comment",
    )
    bundle_root: Optional[str] = Field(
        title="Folder at the root of your project where artifacts necessary to perform the bundle step are stored.",
        default="output/bundle/",
    )
    deploy_root: Optional[str] = Field(
        title="Folder at the root of your project where the bundle step copies the artifacts.",
        default="output/deploy/",
    )
    generated_root: Optional[str] = Field(
        title="Subdirectory of the deploy root where files generated by the Snowflake CLI will be written.",
        default="__generated/",
    )
    scratch_stage: Optional[str] = Field(
        title="Identifier of the stage that stores temporary scratch data used by the Snowflake CLI.",
        default="app_src.stage_snowflake_cli_scratch",
    )

    @field_validator("source_stage")
    @classmethod
    def validate_source_stage(cls, input_value: str):
        if not re.match(DB_SCHEMA_AND_NAME, input_value):
            raise ValueError("Incorrect value for source_stage value")
        return input_value

    @field_validator("spec")
    @classmethod
    def transform_artifacts(
        cls, orig_artifacts: Union[PathMapping, str]
    ) -> PathMapping:
        return (
            PathMapping(src=orig_artifacts)
            if orig_artifacts and isinstance(orig_artifacts, str)
            else orig_artifacts
        )

    @field_validator("images")
    @classmethod
    def transform_images(
        cls, orig_artifacts: List[Union[PathMapping, str]]
    ) -> List[PathMapping]:
        transformed_artifacts = []
        if orig_artifacts is None:
            return transformed_artifacts

        for artifact in orig_artifacts:
            if isinstance(artifact, PathMapping):
                transformed_artifacts.append(artifact)
            else:
                transformed_artifacts.append(PathMapping(src=artifact))

        return transformed_artifacts
