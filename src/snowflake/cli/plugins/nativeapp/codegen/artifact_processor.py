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
from pathlib import Path
from typing import Optional

from click import ClickException
from snowflake.cli.api.project.schemas.native_app.path_mapping import (
    PathMapping,
    ProcessorMapping,
)
from snowflake.cli.plugins.nativeapp.project_model import NativeAppProjectModel


class UnsupportedArtifactProcessorError(ClickException):
    """Exception thrown when a user has passed in an unsupported artifact processor."""

    def __init__(self, processor_name: str):
        super().__init__(
            f"Unsupported value {processor_name} detected for an artifact processor. Please refer to documentation for a list of supported types."
        )


def is_python_file_artifact(src: Path, _: Path):
    """Determines whether the provided source path is an existing python file."""
    return src.is_file() and src.suffix == ".py"


class ProjectFileContextManager:
    def __init__(self, path: Path):
        self.path = path
        self.contents = None
        self.edited_contents = None

    def __enter__(self):
        with open(self.path, "r", encoding="utf-8") as f:
            self.contents = f.read()

        if self.path.is_symlink():
            # if the file is a symlink, make sure we don't overwrite the original
            self.path.unlink()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.edited_contents is not None:
            with open(self.path, "w", encoding="utf-8") as f:
                f.write(self.edited_contents)


class ArtifactProcessor(ABC):
    def __init__(
        self,
        na_project: NativeAppProjectModel,
    ) -> None:
        self._na_project = na_project

    @abstractmethod
    def process(
        self,
        artifact_to_process: PathMapping,
        processor_mapping: Optional[ProcessorMapping],
        **kwargs,
    ) -> None:
        pass

    def edit_file(self, path: Path):
        return ProjectFileContextManager(path)
