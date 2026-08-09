"""SessionStore in isolation: input rejection, append semantics, trigger
policy, and ensure_ascii persistence.

The session layer was only exercised through SessionService; the store's own
guards (empty-id rejection, missing-session, non-dict entry), its copy-on-append
behavior, the hash-mode trigger digest, and non-ASCII round-tripping were
untested. Hermetic: everything runs against a temp directory.
"""

import hashlib
import unittest
import uuid
from pathlib import Path

from core.sapphire.session_store import SessionStore


class SessionStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp_root = Path("tmp_axis_boundary_tests") / str(uuid.uuid4())
        self.tmp_root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(self._cleanup_tmp_root)
        self.store = SessionStore(root_dir=self.tmp_root / "sessions")

    def _cleanup_tmp_root(self):
        if not self.tmp_root.exists():
            return
        for path in sorted(self.tmp_root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                path.rmdir()
        self.tmp_root.rmdir()

    # ---- create_session ----

    def test_create_session_rejects_blank_operator_id(self):
        for bad in ("", "   ", None):
            with self.assertRaises(ValueError) as ctx:
                self.store.create_session(bad)
            self.assertIn("operator_id is required", str(ctx.exception))

    def test_create_session_strips_and_persists(self):
        session = self.store.create_session("  op_1  ")
        self.assertEqual(session["operator_id"], "op_1")
        self.assertEqual(len(session["session_id"]), 32)  # uuid4().hex
        self.assertEqual(session["entries"], [])
        self.assertIn("created_at", session)
        loaded = self.store.get_session(session["session_id"])
        self.assertEqual(loaded["operator_id"], "op_1")
        self.assertEqual(loaded["session_id"], session["session_id"])

    # ---- get_session ----

    def test_get_session_rejects_blank_session_id(self):
        for bad in ("", "   ", None):
            with self.assertRaises(ValueError) as ctx:
                self.store.get_session(bad)
            self.assertIn("session_id is required", str(ctx.exception))

    def test_get_session_returns_none_for_unknown_id(self):
        self.assertIsNone(self.store.get_session("no-such-session"))

    # ---- append_entry ----

    def test_append_entry_rejects_blank_session_id(self):
        for bad in ("", "   ", None):
            with self.assertRaises(ValueError) as ctx:
                self.store.append_entry(bad, {"x": 1})
            self.assertIn("session_id is required", str(ctx.exception))

    def test_append_entry_rejects_missing_session(self):
        with self.assertRaises(ValueError) as ctx:
            self.store.append_entry("no-such-session", {"x": 1})
        self.assertIn("Session not found: no-such-session", str(ctx.exception))

    def test_append_entry_rejects_non_dict_entry(self):
        sid = self.store.create_session("op_1")["session_id"]
        for bad in ("string", ["a"], 1, None):
            with self.assertRaises(ValueError) as ctx:
                self.store.append_entry(sid, bad)
            self.assertIn("entry must be a dictionary", str(ctx.exception))

    def test_append_entry_stores_a_copy_and_preserves_order(self):
        sid = self.store.create_session("op_1")["session_id"]
        entry = {"result": "first"}
        self.store.append_entry(sid, entry)
        entry["result"] = "MUTATED"  # mutating the caller's dict must not leak
        self.store.append_entry(sid, {"result": "second"})
        loaded = self.store.get_session(sid)
        self.assertEqual([e["result"] for e in loaded["entries"]], ["first", "second"])

    # ---- _trigger_field policy ----

    def test_trigger_field_full_mode_returns_stripped_trigger(self):
        self.assertEqual(self.store._trigger_field("  do thing  "), {"trigger": "do thing"})

    def test_trigger_field_hash_mode_returns_exact_16_char_digest(self):
        hashed = SessionStore(root_dir=self.tmp_root / "hashed", store_full_trigger=False)
        result = hashed._trigger_field("Sensitive text")
        expected = hashlib.sha256("Sensitive text".encode("utf-8")).hexdigest()[:16]
        self.assertEqual(result, {"trigger_hash": expected})
        self.assertEqual(len(result["trigger_hash"]), 16)
        self.assertNotIn("trigger", result)

    def test_trigger_field_rejects_blank_trigger(self):
        for bad in ("", "   ", None):
            with self.assertRaises(ValueError) as ctx:
                self.store._trigger_field(bad)
            self.assertIn("trigger is required", str(ctx.exception))

    # ---- ensure_ascii persistence ----

    def test_non_ascii_trigger_persists_as_ascii_and_round_trips(self):
        sid = self.store.create_session("op_1")["session_id"]
        trigger = "café ☕ naïve"
        self.store.append_entry(sid, {**self.store._trigger_field(trigger), "result": "ok"})

        raw = (self.tmp_root / "sessions" / f"{sid}.json").read_text(encoding="utf-8")
        self.assertTrue(raw.isascii())          # ensure_ascii=True: file is pure ASCII
        self.assertNotIn("☕", raw)              # no raw non-ASCII char on disk
        self.assertIn("\\u2615", raw)           # persisted as an escape instead

        loaded = self.store.get_session(sid)
        self.assertEqual(loaded["entries"][0]["trigger"], trigger)  # lossless round-trip


if __name__ == "__main__":
    unittest.main()
