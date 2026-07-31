from src.application.ports.media.image_detection_provider import ImageDetectionProvider
from src.domain.media.image_detection_input import ImageDetectionInput
from src.domain.media.image_detection_result import ImageDetectionResult


class DisabledImageDetectionProvider(ImageDetectionProvider):
    def __init__(self, configured_enabled: bool = False) -> None:
        self._configured_enabled = configured_enabled

    @property
    def ready(self) -> bool:
        return False

    @property
    def enabled(self) -> bool:
        return self._configured_enabled

    async def analyze(self, input_image: ImageDetectionInput) -> ImageDetectionResult:
        warning = "image_provider_unavailable" if self._configured_enabled else "image_provider_disabled"
        return ImageDetectionResult(
            attachment_id=input_image.attachment_id,
            model_name="disabled",
            model_version="disabled",
            processing_time_ms=0,
            warnings=(warning,),
        )

