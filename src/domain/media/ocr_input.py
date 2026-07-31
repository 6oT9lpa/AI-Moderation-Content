from pydantic import BaseModel, ConfigDict, Field


class OcrInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    attachment_id: str
    image_bytes: bytes
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    width: int = Field(gt=0)
    height: int = Field(gt=0)

