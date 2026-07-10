from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.contracts.image_attachment_input_schema import ImageAttachmentInputSchema
from src.infrastructure.logging import get_logger
from src.modules.media.media_analyzer import MediaAnalyzer
from src.modules.media.null_ocr_service import NullOcrService
from src.infrastructure.media.tesseract_ocr_service import TesseractOcrService

logger = get_logger(__name__)


async def _analyze(args: argparse.Namespace) -> None:
    image_path = Path(args.image_path).expanduser().resolve()
    if not image_path.is_file():
        raise FileNotFoundError(f"Image file was not found: {image_path}")
    content_type = mimetypes.guess_type(image_path.name)[0] or ""
    if not content_type.startswith("image/"):
        raise ValueError(f"Unsupported image content type: {content_type or 'unknown'}")
    ocr_service = (
        TesseractOcrService(executable_path=args.tesseract_path)
        if args.ocr_engine == "tesseract"
        else NullOcrService()
    )
    attachment = ImageAttachmentInputSchema(
        attachment_id=image_path.stem,
        content_type=content_type,
        file_name=image_path.name,
        file_size=image_path.stat().st_size,
        image_bytes=image_path.read_bytes(),
    )
    logger.info("Manual image analysis started path=%s ocr_engine=%s", image_path, args.ocr_engine)
    result = await MediaAnalyzer(ocr_service=ocr_service).analyze(
        (attachment,),
        message_text=args.message_text,
        account_age_days=args.account_age_days,
    )
    logger.info("Manual image analysis finished path=%s risk_score=%s", image_path, result.risk.score)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze one image through the media moderation pipeline.")
    parser.add_argument("image_path")
    parser.add_argument("--message-text", default="")
    parser.add_argument("--account-age-days", type=int)
    parser.add_argument("--ocr-engine", choices=("none", "tesseract"), default="none")
    parser.add_argument("--tesseract-path")
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(_analyze(_parse_args()))
