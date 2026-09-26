"""Boundary-violation log redaction contract.

The violation log is written to disk and inspected by operators, so its
structure-only snapshots are the guarantee that raw sensitive values (trigger
text, classifications, answers) never land in a log line. These limits and the
list/tuple item path were previously only shallowly exercised.
"""

import json
import unittest
import uuid
from pathlib import Path
from unittest import mock

from core.security import violations
from core.security.violations import _payload_snapshot, log_boundary_violation


class PayloadSnapshotRedactionTests(unittest.TestCase):
    def test_none_and_scalars_record_type_not_value(self):
        self.assertIsNone(_payload_snapshot(None))
        self.assertEqual(_payload_snapshot("secret"), {"type": "str", "length": 6})
        # bool is matched before int, so True/False never report as int.
        self.assertEqual(_payload_snapshot(True), {"type": "bool"})
        self.assertEqual(_payload_snapshot(False), {"type": "bool"})
        self.assertEqual(_payload_snapshot(42), {"type": "int"})
        self.assertEqual(_payload_snapshot(3.14), {"type": "float"})
        for value in ("secret", 42, 3.14):
            self.assertNotIn(str(value), json.dumps(_payload_snapshot(value)))

    def test_dict_keeps_only_fixed_label_keys_and_values_are_shape_only(self):
        # S2: caller-controlled key names are counted, never written; fixed
        # labels (e.g. AXIS field names) keep their names.
        snap = _payload_snapshot({"password": "hunter2", "count": 5, "trigger": "t"})
        self.assertEqual(snap["type"], "dict")
        self.assertEqual(snap["size"], 3)
        self.assertEqual(snap["keys"], ["trigger"])
        self.assertEqual(snap["value_shapes"], {"trigger": {"type": "str", "length": 1}})
        self.assertEqual(snap["other_key_count"], 2)
        self.assertEqual(snap["other_value_shapes"], [{"type": "str", "length": 7}, {"type": "int"}])
        dumped = json.dumps(snap)
        self.assertNotIn("hunter2", dumped)
        self.assertNotIn("password", dumped)
        self.assertNotIn("count", dumped.replace("other_key_count", ""))

    def test_non_string_dict_keys_are_counted_not_written(self):
        snap = _payload_snapshot({42: "secret"})
        self.assertEqual(snap["keys"], [])
        self.assertEqual(snap["value_shapes"], {})
        self.assertEqual(snap["other_key_count"], 1)
        self.assertEqual(snap["other_value_shapes"], [{"type": "str", "length": 6}])
        self.assertNotIn("secret", json.dumps(snap))
        self.assertNotIn("42", json.dumps(snap))

    def test_list_items_are_shape_only(self):
        items = ["alpha-secret", "beta-secret"]
        snap = _payload_snapshot(items)
        self.assertEqual(snap["type"], "list")
        self.assertEqual(snap["length"], 2)
        self.assertEqual(
            snap["item_shapes"],
            [
                {"type": "str", "length": len(items[0])},
                {"type": "str", "length": len(items[1])},
            ],
        )
        dumped = json.dumps(snap)
        self.assertNotIn("alpha-secret", dumped)
        self.assertNotIn("beta-secret", dumped)

    def test_tuple_is_labeled_tuple_and_items_shape_only(self):
        snap = _payload_snapshot(("x", "secret-y"))
        self.assertEqual(snap["type"], "tuple")
        self.assertEqual(snap["length"], 2)
        self.assertEqual(snap["item_shapes"][1], {"type": "str", "length": len("secret-y")})
        self.assertNotIn("secret-y", json.dumps(snap))

    def test_list_sampled_to_20_items_but_length_is_full(self):
        snap = _payload_snapshot([f"secret-{i}" for i in range(25)])
        self.assertEqual(snap["length"], 25)
        self.assertEqual(len(snap["item_shapes"]), 20)
        self.assertTrue(all(shape["type"] == "str" for shape in snap["item_shapes"]))
        self.assertNotIn("secret-", json.dumps(snap))

    def test_other_keys_counted_in_full_value_shapes_sampled_at_20(self):
        snap = _payload_snapshot({f"k{i}": f"v{i}" for i in range(60)})
        self.assertEqual(snap["size"], 60)
        self.assertEqual(snap["keys"], [])
        self.assertEqual(snap["other_key_count"], 60)
        self.assertEqual(len(snap["other_value_shapes"]), 20)
        # Neither values nor caller key names leak, even for sampled entries.
        self.assertNotIn("v0", json.dumps(snap))
        self.assertNotIn("k0", json.dumps(snap))

    def test_max_depth_truncates_without_leaking_deep_value(self):
        payload = {"l1": {"l2": {"l3": {"l4": "DEEP-SECRET"}}}}
        snap = _payload_snapshot(payload)
        # Caller key names are not written, so the path is positional.
        deepest = (
            snap["other_value_shapes"][0]["other_value_shapes"][0]
            ["other_value_shapes"][0]["other_value_shapes"][0]
        )
        self.assertEqual(deepest, {"type": "truncated", "reason": "max_depth"})
        self.assertNotIn("DEEP-SECRET", json.dumps(snap))
        self.assertNotIn("l1", json.dumps(snap))

    def test_unknown_types_record_type_name_only(self):
        self.assertEqual(_payload_snapshot(b"secret-bytes"), {"type": "bytes"})
        self.assertEqual(_payload_snapshot({1, 2, 3}), {"type": "set"})
        self.assertNotIn("secret-bytes", json.dumps(_payload_snapshot(b"secret-bytes")))


class LogBoundaryViolationTests(unittest.TestCase):
    def setUp(self):
        self.tmp_root = Path("tmp_axis_boundary_tests") / str(uuid.uuid4())
        self.tmp_root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(self._cleanup_tmp_root)
        self.log_path = self.tmp_root / "logs" / "sapphire_boundary_violations.log"
        patch = mock.patch.object(violations, "VIOLATION_LOG_PATH", self.log_path)
        patch.start()
        self.addCleanup(patch.stop)

    def _cleanup_tmp_root(self):
        if not self.tmp_root.exists():
            return
        for path in sorted(self.tmp_root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                path.rmdir()
        self.tmp_root.rmdir()

    def _read_lines(self):
        if not self.log_path.exists():
            return []
        return [line for line in self.log_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def test_appends_one_ordered_jsonl_line_per_call(self):
        for vtype in ("first", "second", "third"):
            log_boundary_violation(violation_type=vtype)
        lines = self._read_lines()
        self.assertEqual(len(lines), 3)
        parsed = [json.loads(line) for line in lines]
        self.assertEqual([e["violation_type"] for e in parsed], ["first", "second", "third"])
        self.assertTrue(all(e["component"] == "sapphire_boundary" for e in parsed))

    def test_logged_entry_redacts_payload_and_details_values(self):
        log_boundary_violation(
            violation_type="t",
            endpoint="POST /api/v2/execute",
            operator_id="op-1",
            payload={"secret_value": "TOP-SECRET"},
            details={"field": "trigger"},
        )
        raw = self._read_lines()[-1]
        entry = json.loads(raw)
        # Endpoint is stored raw; the operator ID only as presence; payload and
        # details are structure-only and caller key names are not written.
        self.assertNotIn("operator_id", entry)
        self.assertTrue(entry["operator_id_present"])
        self.assertNotIn("op-1", raw)
        self.assertEqual(entry["endpoint"], "POST /api/v2/execute")
        self.assertEqual(entry["payload_snapshot"]["other_key_count"], 1)
        self.assertEqual(
            entry["payload_snapshot"]["other_value_shapes"],
            [{"type": "str", "length": 10}],
        )
        self.assertNotIn("secret_value", raw)
        self.assertEqual(entry["details"]["value_shapes"]["field"]["type"], "str")
        self.assertNotIn("TOP-SECRET", raw)

    def test_return_value_matches_persisted_line(self):
        entry = log_boundary_violation(violation_type="t", payload={"a": 1})
        self.assertEqual(json.loads(self._read_lines()[-1]), entry)


if __name__ == "__main__":
    unittest.main()
