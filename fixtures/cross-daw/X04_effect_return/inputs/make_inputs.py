"""Regenerate the binary/derived X04 inputs from their committed sources.

Two jobs, both stdlib-only:

1. ``cubase/x04.dawproject`` — zip ``x04_project.xml`` (+ a minimal
   ``metadata.xml``) into the DAWproject container the Cubase adapter parses.
2. ``logic/*.wav`` — synthesize the two tiny evidence stems (quiet tones, same
   stdlib ``wave`` approach as the Logic repo's demo). They exist only so the
   evidence pipeline has real files to scan and hash; they are clearly
   synthetic, and the fixture's intent.md says so.

Run from anywhere:

    python fixtures/cross-daw/X04_effect_return/inputs/make_inputs.py
"""

from __future__ import annotations

import math
import struct
import wave
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

METADATA_XML = '<?xml version="1.0" encoding="UTF-8"?>\n<MetaData/>'

# (filename, frequency_hz) — quiet sine stems; deterministic output.
LOGIC_STEMS = [
    ("Lead Vox.wav", 440.0),
    ("Reverb Return.wav", 330.0),
]


def build_dawproject() -> Path:
    src = HERE / "cubase" / "x04_project.xml"
    out = HERE / "cubase" / "x04.dawproject"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        # Fixed date_time keeps the zip byte-stable across regenerations.
        info = zipfile.ZipInfo("project.xml", date_time=(2026, 1, 1, 0, 0, 0))
        zf.writestr(info, src.read_text(encoding="utf-8"))
        meta = zipfile.ZipInfo("metadata.xml", date_time=(2026, 1, 1, 0, 0, 0))
        zf.writestr(meta, METADATA_XML)
    return out


def write_tone_wav(path: Path, freq: float, *, seconds: float = 1.0, sr: int = 22050) -> None:
    n = int(seconds * sr)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for i in range(n):
            t = i / sr
            env = min(1.0, t * 8) * max(0.0, 1.0 - (t / seconds) ** 2)
            sample = 0.1 * env * math.sin(2 * math.pi * freq * t)
            frames += struct.pack("<h", int(sample * 32767))
        wf.writeframes(bytes(frames))


def main() -> None:
    out = build_dawproject()
    print(f"wrote {out}")
    for name, freq in LOGIC_STEMS:
        path = HERE / "logic" / name
        write_tone_wav(path, freq)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
