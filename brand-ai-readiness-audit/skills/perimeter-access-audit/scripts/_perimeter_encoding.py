"""Content-Encoding decompression for perimeter-access-audit's fetch layer — split out of check_perimeter.py since both PER-03's edge probing and PER-11's content-parity fetch need it independently of the robots.txt/llms.txt fetch path.
"""

from __future__ import annotations

import zlib

_MAX_DECOMPRESSED_BYTES = 20_000_000


def decode_content_encoding(raw: bytes, content_encoding: str) -> bytes:
    """Undo Content-Encoding before the body is treated as text.

    `urllib.request` never auto-decompresses (unlike `requests`), and some
    CDNs gzip responses regardless of whether the client's Accept-Encoding
    advertised support for it — observed live against python.org: raw gzip
    bytes were decoded as UTF-8 text and treated as robots.txt/llms.txt
    content, producing binary garbage that every downstream check kept
    processing rather than failing loudly on, because nothing checked for
    this. Bounded to guard against a decompression-bomb response.
    """
    tokens = [t.strip().lower() for t in (content_encoding or "").split(",") if t.strip()]
    for token in reversed(tokens):
        if token in ("gzip", "x-gzip"):
            raw = _bounded_decompress(zlib.decompressobj(zlib.MAX_WBITS | 16), raw)
        elif token == "deflate":
            raw = _bounded_decompress(zlib.decompressobj(), raw)
        elif token in ("identity", ""):
            continue
        else:
            raise ValueError(f"unsupported Content-Encoding {token!r}; refusing to guess")
    return raw


def _bounded_decompress(decompressor, raw: bytes) -> bytes:
    output = decompressor.decompress(raw, _MAX_DECOMPRESSED_BYTES)
    if decompressor.unconsumed_tail:
        raise ValueError(f"decompressed body exceeds {_MAX_DECOMPRESSED_BYTES} bytes")
    return output + decompressor.flush()


def _best_effort_decode_content_encoding(raw: bytes, content_encoding: str) -> bytes:
    """Lenient variant for `probe_with_user_agent`, which reads a truncated
    4096-byte prefix for classification purposes only — a truncated gzip
    stream can legitimately fail to decompress even though the response was
    fine. Falls back to the raw bytes (today's behaviour) rather than
    treating a decompression hiccup on a deliberately-truncated read as a
    fetch failure; `classify_response`'s "ambiguous" path already covers text
    that fails to look like anything recognisable."""
    try:
        return decode_content_encoding(raw, content_encoding)
    except Exception:
        return raw
