"""Defense-in-depth sanitization for the dataset export (master-prompt §57).

Adapter bundles are *already* home-dir-sanitized at export time; this module is
the dataset builder's second line of defense plus its asset-path hasher and
aggregate-packaging scrubber. Three public operations:

- :func:`redact_paths` — replace home directories (``/Users/<u>``,
  ``/home/<u>``, ``\\Users\\<u>``), ``/Volumes/<mount>`` prefixes and the live
  username with ``<redacted>`` wherever they appear inside a string (prose
  included).
- :func:`hash_asset_path` — content-address a path/filename string to a stable
  ``asset:sha256:<12hex>`` token, so a media reference travels as an opaque,
  reproducible id and never as a filesystem path (or a leaking ``.wav`` name).
- :func:`sanitize_snapshot` / :func:`sanitize_native` — deep-copy a snapshot or
  a native payload and rewrite every leaf string: path-like values are hashed,
  everything else is path-redacted. Ids and cross-references are never path-like
  in a valid snapshot, so referential integrity survives the rewrite (the export
  re-validates every snapshot to prove it).

The transforms are pure and deterministic: the same input always yields the same
output, so a rebuilt dataset diffs cleanly.
"""

from __future__ import annotations

import copy
import getpass
import hashlib
import os
import re
from pathlib import Path
from typing import Any

try:  # posix only; absent on Windows
    import pwd
except ImportError:  # pragma: no cover - platform dependent
    pwd = None  # type: ignore[assignment]

REDACTED = "<redacted>"
ASSET_PREFIX = "asset:sha256:"
_ASSET_HEX_LEN = 12

# Media / project / session-asset extensions whose presence marks a string as a
# file reference (and, for the audio ones, a leak the scan forbids outright).
_ASSET_EXTS: tuple[str, ...] = (
    "wav", "wave", "aif", "aiff", "aifc", "flac", "mp3", "m4a", "aac",
    "ogg", "oga", "opus", "caf", "rex", "rx2",
    "rpp", "als", "adg", "logicx", "dawproject", "cpr", "npr", "song",
    "flp", "ptx", "ptf",
    "mid", "midi", "mov", "mp4", "m4v", "wmv",
)
_EXT_ALTERNATION = "|".join(_ASSET_EXTS)

# A trailing asset extension marks the *whole* string as a file reference.
_TRAILING_EXT_RE = re.compile(r"\.(?:" + _EXT_ALTERNATION + r")\s*$", re.IGNORECASE)

# An embedded asset-filename token (a ``.wav`` named mid-sentence, say). Matched
# so a leak that is not the whole string is still hashed out, prose preserved.
_MEDIA_TOKEN_RE = re.compile(
    r"[\w.\-/\\]+\.(?:" + _EXT_ALTERNATION + r")\b", re.IGNORECASE
)

# A bare filesystem path: posix absolute/relative, home (~), or Windows drive.
_PATH_SHAPE_RE = re.compile(r"^(?:/|\./|\.\./|~/|~$|[A-Za-z]:[\\/])")

# Home / volume path tokens redacted anywhere in a string (marker + the private
# first segment; any neutral tail is cleaned by asset-hashing if it still reads
# as a path).
_HOME_TOKEN_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"/Users/[^/\s\"']+"),
    re.compile(r"/home/[^/\s\"']+"),
    re.compile(r"\\Users\\[^\\\s\"']+"),
    re.compile(r"/Volumes/[^/\s\"']+"),
)


def _username_candidates() -> set[str]:
    """Every plausible spelling of the live username, for redaction."""
    names: set[str] = set()
    try:
        names.add(getpass.getuser())
    except Exception:  # noqa: BLE001 - getuser can raise with no controlling tty
        pass
    if pwd is not None:
        try:
            names.add(pwd.getpwuid(os.getuid()).pw_name)
        except Exception:  # noqa: BLE001
            pass
    try:
        names.add(Path.home().name)
    except Exception:  # noqa: BLE001
        pass
    for var in ("USER", "USERNAME", "LOGNAME"):
        value = os.environ.get(var)
        if value:
            names.add(value)
    # Guard against redacting a 1-2 char string that collides with real content.
    return {n for n in names if n and len(n) >= 3}


_USERNAME_RES: tuple[re.Pattern[str], ...] = tuple(
    re.compile(r"\b" + re.escape(name) + r"\b") for name in sorted(_username_candidates())
)


def redact_paths(text: str) -> str:
    """Redact home dirs, ``/Volumes`` mounts, Windows paths and the username.

    A pure substring transform: only strings that actually contain one of the
    markers change, so it is safe to apply to any string, prose included.
    """
    if not isinstance(text, str) or not text:
        return text
    out = text
    for rx in _HOME_TOKEN_RES:
        out = rx.sub(REDACTED, out)
    for rx in _USERNAME_RES:
        out = rx.sub(REDACTED, out)
    return out


def hash_asset_path(path: str) -> str:
    """Content-address a path string to a stable ``asset:sha256:<12hex>`` token."""
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:_ASSET_HEX_LEN]
    return ASSET_PREFIX + digest


def _looks_like_asset(text: str) -> bool:
    """True when the whole string reads as a file path or asset filename."""
    stripped = text.strip()
    if not stripped:
        return False
    if _TRAILING_EXT_RE.search(stripped):
        return True
    if _PATH_SHAPE_RE.match(stripped):
        return True
    return False


def _sanitize_string(value: str) -> str:
    """Sanitize one leaf string: hash asset paths, redact the rest."""
    redacted = redact_paths(value)
    if _looks_like_asset(redacted):
        return hash_asset_path(redacted)
    # Neutralize any residual media-filename token embedded in otherwise-clean
    # prose (defense-in-depth: keeps a mid-sentence ``.wav`` out of the export).
    return _MEDIA_TOKEN_RE.sub(lambda m: hash_asset_path(m.group(0)), redacted)


def sanitize_json(obj: Any) -> Any:
    """Deep-sanitize any JSON-like structure, returning a fresh copy.

    Every string leaf *and dict key* is passed through :func:`_sanitize_string`;
    containers are rebuilt rather than mutated, so the input is never touched.
    Schema field names and entity ids are not path-shaped, so they pass through
    unchanged and referential / schema integrity is preserved.
    """
    if isinstance(obj, dict):
        return {
            (_sanitize_string(k) if isinstance(k, str) else k): sanitize_json(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [sanitize_json(v) for v in obj]
    if isinstance(obj, tuple):
        return [sanitize_json(v) for v in obj]
    if isinstance(obj, str):
        return _sanitize_string(obj)
    return obj


def sanitize_snapshot(snap_dict: dict) -> dict:
    """Deep-sanitize a canonical snapshot dict; returns a new dict, input intact.

    Walks the whole structure (a superset of ``entity.properties``,
    ``entity.native.properties``, ``provenance[].source_ref``/``explanation`` and
    ``extensions``): path-like string values are hashed to ``asset:sha256:`` and
    every other string is path-redacted. Deterministic, and safe to re-validate.
    """
    return sanitize_json(copy.deepcopy(snap_dict))


def sanitize_native(native_dict: dict) -> dict:
    """Deep-sanitize a ``native.json`` payload; same treatment as the snapshot."""
    return sanitize_json(copy.deepcopy(native_dict))
