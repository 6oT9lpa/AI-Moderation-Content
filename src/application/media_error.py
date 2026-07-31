class MediaError(Exception):
    """Base error with a stable, API-safe code."""

    code = "media_error"


class MediaValidationError(MediaError):
    code = "media_validation_failed"


class UnsupportedMediaError(MediaValidationError):
    code = "unsupported_media"


class MediaSecurityError(MediaValidationError):
    code = "media_security_rejected"


class MediaDownloadUnavailableError(MediaError):
    code = "media_download_unavailable"


class MediaDownloadTimeoutError(MediaDownloadUnavailableError):
    code = "media_download_timeout"


class MediaModelUnavailableError(MediaError):
    code = "media_model_unavailable"


class MediaInferenceError(MediaError):
    code = "media_inference_failed"


class MediaPersistenceError(MediaError):
    code = "media_persistence_failed"

