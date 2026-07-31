from pydantic import BaseModel, ConfigDict, Field


class MediaHashes(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    phash: str = Field(pattern=r"^[0-9a-f]{16}$")
    dhash: str = Field(pattern=r"^[0-9a-f]{16}$")
    ahash: str = Field(pattern=r"^[0-9a-f]{16}$")

