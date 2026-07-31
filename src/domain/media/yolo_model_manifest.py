import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class YoloModelManifest(BaseModel):
    """Immutable contract between the external MIT trainer and our ONNX runtime."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    schema_version: str = Field(pattern=r"^1$")
    model_name: str = Field(min_length=1, max_length=128)
    model_version: str = Field(min_length=1, max_length=128)
    license: str = Field(pattern=r"^MIT$")
    source_repository: str = Field(pattern=r"^https://github\.com/MultimediaTechLab/YOLO(?:\.git)?$")
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    onnx_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_size: int = Field(strict=True, ge=320, le=1280)
    class_names: tuple[str, ...] = Field(min_length=1, max_length=128)
    output_layout: str = Field(pattern=r"^(xywh_objectness_classes|xywh_classes)$")
    output_transposed: bool = False

    @field_validator("class_names", mode="before")
    @classmethod
    def deserialize_classes(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def unique_classes(self) -> "YoloModelManifest":
        if len(set(self.class_names)) != len(self.class_names):
            raise ValueError("YOLO class names must be unique")
        return self

    @classmethod
    def load_verified(cls, model_dir: Path) -> "YoloModelManifest":
        payload = json.loads((model_dir / "manifest.json").read_text(encoding="utf-8"))
        manifest = cls.model_validate(payload)
        actual = hashlib.sha256((model_dir / "model.onnx").read_bytes()).hexdigest()
        if actual != manifest.onnx_sha256:
            raise ValueError("YOLO ONNX checksum mismatch")
        return manifest
