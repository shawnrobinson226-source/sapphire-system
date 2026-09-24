"""distortion_lock completeness: the JSON-contract source path and the
version-mismatch enforcement, which the two existing tests do not exercise
(they only hit the .ts regex path with a class-set mismatch).

All tests pass an explicit temp source_path, so the module-level default
AXIS_DISTORTION_SOURCE (absent from the repo) is never used -- fully hermetic.
"""

import json
import unittest
import uuid
from pathlib import Path

from core.sapphire import distortion_lock


class DistortionLockCompletenessTests(unittest.TestCase):
    def setUp(self):
        self.tmp_root = Path("tmp_axis_boundary_tests") / str(uuid.uuid4())
        self.tmp_root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(self._cleanup_tmp_root)

    def _cleanup_tmp_root(self):
        if not self.tmp_root.exists():
            return
        for path in sorted(self.tmp_root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                path.rmdir()
        self.tmp_root.rmdir()

    def _write(self, name, text):
        path = self.tmp_root / name
        path.write_text(text, encoding="utf-8")
        return path

    def _write_json(self, name, obj):
        return self._write(name, json.dumps(obj))

    def _ts(self, version_line, classes):
        joined = ", ".join(f"'{c}'" for c in classes)
        body = f"export const DISTORTION_TYPES = [{joined}];\n"
        return (version_line + body) if version_line else body

    # ---- JSON-contract source path (previously untested) ----

    def test_json_source_in_sync_passes(self):
        path = self._write_json(
            "contract.json",
            {
                "distortion_class_version": distortion_lock.DISTORTION_CLASS_VERSION,
                "distortion_classes": list(distortion_lock.ALLOWED_DISTORTION_CLASSES),
            },
        )
        self.assertTrue(distortion_lock.assert_distortion_sync(path))

    def test_json_source_missing_class_fails(self):
        classes = [c for c in distortion_lock.ALLOWED_DISTORTION_CLASSES if c != "continuity"]
        path = self._write_json(
            "contract.json",
            {
                "distortion_class_version": distortion_lock.DISTORTION_CLASS_VERSION,
                "distortion_classes": classes,
            },
        )
        with self.assertRaises(RuntimeError) as ctx:
            distortion_lock.assert_distortion_sync(path)
        self.assertIn("Distortion class mismatch", str(ctx.exception))
        self.assertIn("continuity", str(ctx.exception))

    def test_json_source_extra_class_fails(self):
        path = self._write_json(
            "contract.json",
            {
                "distortion_class_version": distortion_lock.DISTORTION_CLASS_VERSION,
                "distortion_classes": list(distortion_lock.ALLOWED_DISTORTION_CLASSES) + ["malicious"],
            },
        )
        with self.assertRaises(RuntimeError) as ctx:
            distortion_lock.assert_distortion_sync(path)
        self.assertIn("Distortion class mismatch", str(ctx.exception))
        self.assertIn("malicious", str(ctx.exception))

    def test_json_source_version_mismatch_fails(self):
        path = self._write_json(
            "contract.json",
            {
                "distortion_class_version": "axis-distortion-contract-v2",
                "distortion_classes": list(distortion_lock.ALLOWED_DISTORTION_CLASSES),
            },
        )
        with self.assertRaises(RuntimeError) as ctx:
            distortion_lock.assert_distortion_sync(path)
        self.assertIn("Distortion class version mismatch", str(ctx.exception))
        self.assertIn(distortion_lock.DISTORTION_CLASS_VERSION, str(ctx.exception))

    def test_json_source_without_version_skips_version_check(self):
        path = self._write_json(
            "contract.json",
            {"distortion_classes": list(distortion_lock.ALLOWED_DISTORTION_CLASSES)},
        )
        self.assertTrue(distortion_lock.assert_distortion_sync(path))

    def test_json_distortion_classes_not_a_list_raises(self):
        path = self._write_json(
            "contract.json",
            {
                "distortion_class_version": distortion_lock.DISTORTION_CLASS_VERSION,
                "distortion_classes": "narrative",
            },
        )
        with self.assertRaises(RuntimeError) as ctx:
            distortion_lock.assert_distortion_sync(path)
        self.assertIn("distortion_classes must be a list", str(ctx.exception))

    def test_json_classes_are_stringified_and_stripped(self):
        path = self._write_json(
            "contract.json",
            {
                "distortion_class_version": distortion_lock.DISTORTION_CLASS_VERSION,
                "distortion_classes": ["  narrative  ", "emotional", "behavioral", "perceptual", "continuity"],
            },
        )
        self.assertTrue(distortion_lock.assert_distortion_sync(path))

    # ---- .ts / regex source path: version enforcement (previously untested) ----

    def test_ts_source_version_mismatch_fails(self):
        path = self._write(
            "distortion-types.ts",
            self._ts(
                "export const DISTORTION_CLASS_VERSION = 'axis-distortion-contract-v2';\n",
                distortion_lock.ALLOWED_DISTORTION_CLASSES,
            ),
        )
        with self.assertRaises(RuntimeError) as ctx:
            distortion_lock.assert_distortion_sync(path)
        self.assertIn("Distortion class version mismatch", str(ctx.exception))

    def test_ts_source_without_version_skips_version_check(self):
        path = self._write(
            "distortion-types.ts",
            self._ts(None, distortion_lock.ALLOWED_DISTORTION_CLASSES),
        )
        self.assertTrue(distortion_lock.assert_distortion_sync(path))

    # ---- missing source ----

    def test_missing_source_raises(self):
        path = self.tmp_root / "does_not_exist.json"
        with self.assertRaises(RuntimeError) as ctx:
            distortion_lock.assert_distortion_sync(path)
        self.assertIn("AXIS distortion source missing", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
