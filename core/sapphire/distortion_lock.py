"""Sapphire-side lock to ensure distortion taxonomy stays synced with AXIS."""

from __future__ import annotations

import re
from pathlib import Path

DISTORTION_CLASS_VERSION = "axis-v2-locked"
ALLOWED_DISTORTION_CLASSES = (
    "behavioral",
    "cognitive",
    "emotional",
)

AXIS_DISTORTION_SOURCE = Path("lib/kernel/distortion-types.ts")


def _extract_axis_version(source_text: str) -> str | None:
    match = re.search(
        r"DISTORTION_CLASS_VERSION\s*[:=]\s*['\"]([^'\"]+)['\"]",
        source_text,
    )
    return match.group(1).strip() if match else None


def _extract_axis_classes(source_text: str) -> list[str]:
    array_match = re.search(
        r"(?:DISTORTION_TYPES|DISTORTION_CLASSES|ALLOWED_DISTORTION_CLASSES)\s*[:=]\s*\[(.*?)\]",
        source_text,
        flags=re.DOTALL,
    )
    if not array_match:
        raise RuntimeError("Could not find distortion class array in AXIS source.")
    array_block = array_match.group(1)
    classes = re.findall(r"['\"]([^'\"]+)['\"]", array_block)
    if not classes:
        raise RuntimeError("Could not parse distortion classes from AXIS source.")
    return [c.strip() for c in classes if c.strip()]


def assert_distortion_sync(source_path: Path | None = None) -> bool:
    """Fail loudly if Sapphire lock values drift from AXIS source."""
    axis_source = source_path or AXIS_DISTORTION_SOURCE
    if not axis_source.exists():
        raise RuntimeError(f"AXIS distortion source missing: {axis_source}")

    source_text = axis_source.read_text(encoding="utf-8")
    axis_classes = tuple(_extract_axis_classes(source_text))

    if axis_classes != ALLOWED_DISTORTION_CLASSES:
        raise RuntimeError(
            "Distortion class mismatch. "
            f"Sapphire={ALLOWED_DISTORTION_CLASSES}, AXIS={axis_classes}"
        )

    axis_version = _extract_axis_version(source_text)
    if axis_version and axis_version != DISTORTION_CLASS_VERSION:
        raise RuntimeError(
            "Distortion class version mismatch. "
            f"Sapphire={DISTORTION_CLASS_VERSION}, AXIS={axis_version}"
        )

    return True

