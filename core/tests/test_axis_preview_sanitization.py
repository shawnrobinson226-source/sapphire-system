"""DES -> AXIS preview sanitization (build_axis_preview).

build_axis_preview sits at the seam between the DES boundary (transport pinned
in test_des_transport.py, C3) and the AXIS boundary. It is construct-only: it
reads ONLY friction_type and output.output_type from the DES result, derives
classification/next_action from fixed maps, and returns a fresh template dict
filtered to AXIS_PAYLOAD_FIELDS. A hostile DES result that echoes an injected
operator_id / distortion_class / classification / trigger must never carry
those through, because those fields are never read.
"""

import unittest

from core.des.axis_preview import AXIS_PAYLOAD_FIELDS, build_axis_preview
from core.sapphire.distortion_lock import ALLOWED_DISTORTION_CLASSES


DEFAULT_PREVIEW = {
    "trigger": "des_decision_friction",
    "classification": "continuity",
    "next_action": "Review the decision output and choose one clear next step.",
    "reference": True,
    "stability": 6,
    "impact": 4,
}


class AxisPreviewSanitizationTests(unittest.TestCase):
    def test_friction_and_output_map_to_derived_fields(self):
        preview = build_axis_preview(
            {"friction_type": "information_gap", "output": {"output_type": "clarify"}}
        )
        self.assertEqual(preview["classification"], "perceptual")
        self.assertEqual(
            preview["next_action"],
            "Review the clarified decision information and choose one next step.",
        )
        self.assertEqual(preview["trigger"], "des_decision_friction")
        self.assertEqual(set(preview.keys()), AXIS_PAYLOAD_FIELDS)

    def test_none_or_empty_des_result_yields_safe_default(self):
        self.assertEqual(build_axis_preview(None), DEFAULT_PREVIEW)
        self.assertEqual(build_axis_preview({}), DEFAULT_PREVIEW)

    def test_des_fallback_shapes_yield_safe_default(self):
        # Exact DES client fail-closed shapes pinned in test_des_transport.py (C3).
        for fallback in ({"error": "DES unavailable"}, {"show": False}):
            preview = build_axis_preview(fallback)
            self.assertEqual(preview, DEFAULT_PREVIEW)
            self.assertNotIn("error", preview)
            self.assertNotIn("show", preview)
            self.assertNotIn("DES unavailable", repr(preview))

    def test_falsy_output_falls_back_to_defaults(self):
        # `output = des_result.get("output", {}) or {}` guards falsy values.
        for output in (None, False, 0, ""):
            preview = build_axis_preview(
                {"friction_type": "information_gap", "output": output}
            )
            self.assertEqual(preview["classification"], "perceptual")
            self.assertEqual(
                preview["next_action"],
                "Review the decision output and choose one clear next step.",
            )

    def test_injected_operator_id_is_not_carried_through(self):
        preview = build_axis_preview(
            {
                "friction_type": "information_gap",
                "output": {"output_type": "clarify"},
                "operator_id": "attacker-op",
            }
        )
        self.assertNotIn("operator_id", preview)
        self.assertNotIn("attacker-op", repr(preview))

    def test_injected_distortion_class_is_not_carried_through(self):
        preview = build_axis_preview(
            {
                "friction_type": "information_gap",
                "output": {"output_type": "clarify"},
                "distortion_class": "attacker-class",
            }
        )
        self.assertNotIn("distortion_class", preview)
        self.assertNotIn("attacker-class", repr(preview))
        self.assertEqual(preview["classification"], "perceptual")

    def test_injected_classification_is_ignored_in_favor_of_derived(self):
        preview = build_axis_preview(
            {
                "friction_type": "information_gap",
                "output": {"output_type": "clarify"},
                "classification": "operator-controlled-evil",
            }
        )
        self.assertEqual(preview["classification"], "perceptual")
        self.assertNotIn("operator-controlled-evil", repr(preview))

    def test_injected_trigger_in_des_result_is_ignored(self):
        preview = build_axis_preview(
            {
                "friction_type": "information_gap",
                "output": {"output_type": "clarify"},
                "trigger": "attacker-trigger",
            }
        )
        self.assertEqual(preview["trigger"], "des_decision_friction")
        self.assertNotIn("attacker-trigger", repr(preview))

    def test_output_contributes_only_output_type(self):
        preview = build_axis_preview(
            {
                "friction_type": "information_gap",
                "output": {
                    "output_type": "clarify",
                    "operator_id": "attacker-op",
                    "next_action": "attacker-next",
                    "injected": "SECRET-OUTPUT",
                },
            }
        )
        self.assertEqual(
            preview["next_action"],
            "Review the clarified decision information and choose one next step.",
        )
        self.assertNotIn("operator_id", preview)
        for bad in ("attacker-op", "attacker-next", "SECRET-OUTPUT"):
            self.assertNotIn(bad, repr(preview))

    def test_preview_keys_are_exactly_the_axis_allowlist(self):
        hostile = {
            "friction_type": "information_gap",
            "output": {
                "output_type": "clarify",
                "operator_id": "attacker-op",
                "distortion_class": "attacker-class",
                "next_action": "attacker-next",
                "injected": "SECRET-OUTPUT",
            },
            "operator_id": "attacker-op",
            "distortion_class": "attacker-class",
            "classification": "attacker-classification",
            "trigger": "attacker-trigger",
            "interaction_id": "iid-should-not-leak",
            "extra_evil": "SECRET-TOP",
        }
        preview = build_axis_preview(hostile)
        self.assertEqual(set(preview.keys()), AXIS_PAYLOAD_FIELDS)
        # Derived, never copied.
        self.assertEqual(preview["classification"], "perceptual")
        self.assertEqual(preview["trigger"], "des_decision_friction")
        dumped = repr(preview)
        for bad in (
            "attacker-op",
            "attacker-class",
            "attacker-next",
            "SECRET-OUTPUT",
            "attacker-classification",
            "attacker-trigger",
            "iid-should-not-leak",
            "SECRET-TOP",
        ):
            self.assertNotIn(bad, dumped)

    def test_classification_is_always_within_locked_distortion_set(self):
        for friction in (
            "information_gap",
            "fit_uncertainty",
            "trust_deficit",
            "unknown",
            "evil_injected_friction",
            "",
        ):
            preview = build_axis_preview({"friction_type": friction})
            self.assertIn(preview["classification"], ALLOWED_DISTORTION_CLASSES)
        # An unknown/injected friction defaults to the safe 'continuity' class.
        self.assertEqual(
            build_axis_preview({"friction_type": "evil_injected_friction"})["classification"],
            "continuity",
        )


if __name__ == "__main__":
    unittest.main()
