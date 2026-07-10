from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ImageMetadata:
    file_name: str | None
    content_type: str
    file_size: int | None
    width: int | None
    height: int | None
    aspect_ratio: float | None
    is_screenshot_like: bool

    def to_dict(self) -> dict[str, str | int | float | bool | None]:
        return {
            "file_name": self.file_name,
            "content_type": self.content_type,
            "file_size": self.file_size,
            "width": self.width,
            "height": self.height,
            "aspect_ratio": self.aspect_ratio,
            "is_screenshot_like": self.is_screenshot_like,
        }
