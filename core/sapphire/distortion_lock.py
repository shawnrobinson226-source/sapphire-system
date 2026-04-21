"""Sapphire-side lock to ensure distortion taxonomy stays synced with AXIS."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

DISTORTION_CLASS_VERSION = "axis-distortion-contract-v1"
ALLOWED_DISTORTION_CLASSES = (
    "narrative",
    "emotional",
    "behavioral",
    "perceptual",
    "continuity",
)

AXIS_DISTORTION_SOURCE = Path(
    os.environ.get("AXIS_DISTORTION_CONTRACT_PATH", "core/sapphire/axis_distortion_contract_reference.json")
)


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


def _extract_from_json(source_text: str, source_path: Path) -> tuple[str | None, list[str] | None]:
    if source_path.suffix.lower() != ".json":
        return None, None
    data = json.loads(source_text)
    version = data.get("distortion_class_version")
    classes = data.get("distortion_classes")
    if classes is None:
        return version, None
    if not isinstance(classes, list):
        raise RuntimeError("distortion_classes must be a list in AXIS contract reference.")
    clean = [str(c).strip() for c in classes if str(c).strip()]
    return version, clean


def assert_distortion_sync(source_path: Path | None = None) -> bool:
    """Fail loudly if Sapphire lock values drift from AXIS source."""
    axis_source = source_path or AXIS_DISTORTION_SOURCE
    if not axis_source.exists():
        raise RuntimeError(f"AXIS distortion source missing: {axis_source}")

    source_text = axis_source.read_text(encoding="utf-8")
    axis_version, json_classes = _extract_from_json(source_text, axis_source)

    if json_classes is not None:
        axis_classes = tuple(json_classes)
    else:
        axis_classes = tuple(_extract_axis_classes(source_text))
        axis_version = _extract_axis_version(source_text)

    expected = set(ALLOWED_DISTORTION_CLASSES)
    actual = set(axis_classes)

    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise RuntimeError(
            "Distortion class mismatch. "
            f"missing_in_axis={missing}, unexpected_in_axis={extra}, "
            f"Sapphire={ALLOWED_DISTORTION_CLASSES}, AXIS={axis_classes}"
        )

    if axis_version and axis_version != DISTORTION_CLASS_VERSION:
        raise RuntimeError(
            "Distortion class version mismatch. "
            f"Sapphire={DISTORTION_CLASS_VERSION}, AXIS={axis_version}"
        )

    return True
