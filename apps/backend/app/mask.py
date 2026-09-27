import re

_SECRET = re.compile(r"(rtsp://[^:/@\s]+:)([^@/\s]+)@")


def mask_stream_url(url: str | None) -> str | None:
    if not url:
        return url
    return _SECRET.sub(r"\1***@", url)
