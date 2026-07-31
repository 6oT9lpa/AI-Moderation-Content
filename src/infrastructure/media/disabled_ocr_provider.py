from src.application.ports.media.ocr_provider import OcrProvider
from src.domain.media.ocr_input import OcrInput
from src.domain.media.ocr_result import OcrResult


class DisabledOcrProvider(OcrProvider):
    @property
    def ready(self) -> bool:
        return False

    @property
    def enabled(self) -> bool:
        return False

    async def analyze(self, input_image: OcrInput) -> OcrResult:
        return OcrResult(
            attachment_id=input_image.attachment_id,
            model_name="disabled",
            model_version="disabled",
            processing_time_ms=0,
            warnings=("ocr_disabled",),
        )

