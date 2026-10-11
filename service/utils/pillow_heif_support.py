import logging

_REGISTERED = False
_ATTEMPTED = False


def enable_heif_support(logger: logging.Logger | None = None) -> bool:
    global _REGISTERED, _ATTEMPTED
    if _REGISTERED:
        return True
    if _ATTEMPTED:
        return False
    _ATTEMPTED = True
    try:
        from pillow_heif import register_heif_opener  # type: ignore

        register_heif_opener()
        _REGISTERED = True
        if logger:
            logger.info("HEIF/HEIC support enabled via pillow-heif")
        return True
    except Exception as exc:
        if logger:
            logger.warning("HEIF/HEIC support unavailable (install pillow-heif): %s", exc)
        return False
