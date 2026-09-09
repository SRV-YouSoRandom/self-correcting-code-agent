from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

class ArtifactType(str, Enum):
    PNG = "png"
    JPEG = "jpeg"
    CSV = "csv"
    JSON = "json"
    TEXT = "text"
    HTML = "html"
    NONE = "none"

class ArtifactExpectations(BaseModel):
    artifact_type: ArtifactType
    filename: str
    min_size_byte: int = 1
    expected_columns: list[str] = Field(default_factory=list)
    min_row: Optional[int] = None
    min_pixel_variance: Optional[float] = None

    @field_validator("filename")
    @classmethod
    def filename_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("filename must not be empty")
        return value.strip()

class ExecutionContract(BaseModel):
    intent_summary: str
    artifacts: list[ArtifactExpectations] = Field(default_factory=list)
    requires_network: bool = False
    allowed_domains: list[str] = Field(default_factory=list)
    max_execution_seconds: int = 30
    success_criteria: str = ""

    def expects_artifacts(self) -> bool:
        return len(self.artifacts) > 0