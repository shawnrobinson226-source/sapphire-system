import unittest

from core.sapphire.renderer import render_failure, render_gated, render_success


class RendererTests(unittest.TestCase):
    def setUp(self):
        self.success_response = {
            "ok": True,
            "axis": {
                "classification": "stable",
                "protocol": {"steps": ["check input", "run execution", "return result"]},
                "action": "run execution",
                "outcome": "completed",
                "continuity": "session-123",
            },
            "pipeline": {
                "source": "axis_adapter",
                "status_code": 200,
                "internal_note": "should never render",
            },
        }

    def _assert_no_injected_language(self, output: str):
        banned = [
            "you should",
            "i recommend",
            "this means",
            "consider",
            "suggests that",
            "it appears",
        ]
        lower = output.lower()
        for phrase in banned:
            self.assertNotIn(phrase, lower)

    def test_success_response_renders_correctly(self):
        output = render_success(self.success_response)
        self.assertIn("=== AXIS RESULT ===", output)
        self.assertIn("Classification: stable", output)
        self.assertIn("Protocol:", output)
        self.assertIn("1. check input", output)
        self.assertIn("2. run execution", output)
        self.assertIn("3. return result", output)
        self.assertIn("Action:\nrun execution", output)
        self.assertIn("Outcome:\ncompleted", output)
        self.assertIn("Continuity:\nsession-123", output)
        self._assert_no_injected_language(output)

    def test_failure_response_renders_correctly(self):
        output = render_failure(
            {
                "ok": False,
                "error_type": "validation_error",
                "message": "operator_id is required.",
            }
        )
        self.assertEqual(
            output,
            "=== EXECUTION FAILURE ===\nType: validation_error\nMessage: operator_id is required.",
        )
        self._assert_no_injected_language(output)

    def test_failure_renderer_displays_preserved_axis_error_message(self):
        output = render_failure(
            {
                "ok": False,
                "error_type": "axis_error",
                "message": "Guard blocked session",
                "safe_details": {"version": "v2.3.1"},
            }
        )
        self.assertEqual(
            output,
            "=== EXECUTION FAILURE ===\nType: axis_error\nMessage: Guard blocked session",
        )
        self._assert_no_injected_language(output)

    def test_gated_response_renders_correctly(self):
        output = render_gated(
            {
                "ok": True,
                "gated": True,
                "gate_type": "breath",
                "message": "Pause and breathe.",
            }
        )
        self.assertEqual(output, "=== SYSTEM PAUSE === Pause and breathe.")
        self._assert_no_injected_language(output)

    def test_renderer_does_not_mutate_data(self):
        original = {
            "ok": True,
            "axis": {
                "classification": "locked",
                "protocol": ["one", "two"],
                "action": "two",
                "outcome": "done",
                "continuity": "cont",
            },
            "pipeline": {"secret": "x"},
        }
        before = repr(original)
        _ = render_success(original)
        self.assertEqual(repr(original), before)

    def test_protocol_steps_remain_ordered(self):
        response = {
            "ok": True,
            "axis": {
                "classification": "ordered",
                "protocol": ["first", "second", "third"],
                "action": "first",
                "outcome": "ok",
                "continuity": "c",
            },
            "pipeline": {"status_code": 200},
        }
        output = render_success(response)
        pos1 = output.index("1. first")
        pos2 = output.index("2. second")
        pos3 = output.index("3. third")
        self.assertTrue(pos1 < pos2 < pos3)

    def test_renderer_ignores_pipeline_metadata_entirely(self):
        output = render_success(self.success_response)
        self.assertNotIn("axis_adapter", output)
        self.assertNotIn("internal_note", output)
        self.assertNotIn("status_code", output)

    def test_renderer_output_contains_no_injected_language(self):
        output = render_success(self.success_response)
        self._assert_no_injected_language(output)


if __name__ == "__main__":
    unittest.main()
