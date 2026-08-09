"""DES transport boundary: client endpoint/timeout pinning + fail-closed, and
DESFlow interaction_id threading.

core/des/client.py is the real HTTP boundary to the local DES service; every
call must hit only the four 127.0.0.1:8000 paths, carry timeout=3, and fail
closed to a fixed shape when DES is unreachable or returns non-JSON.

Hermeticity: client tests patch core.des.client.requests entirely (no real
network); DESFlow tests patch the client functions as imported into
core.des.service, so the flow never reaches requests at all. Exception-path
tests use the real exception types the bare `except Exception` catches.
"""

import unittest
from unittest import mock

import requests

from core.des import client
from core.des.service import DESFlow


class _FakeResponse:
    def __init__(self, payload=None, json_exc=None):
        self._payload = payload
        self._json_exc = json_exc

    def json(self):
        if self._json_exc is not None:
            raise self._json_exc
        return self._payload


class DESClientTransportTests(unittest.TestCase):
    def test_base_url_is_local_des(self):
        self.assertEqual(client.DES_BASE_URL, "http://127.0.0.1:8000")

    @mock.patch("core.des.client.requests")
    def test_check_health_gets_health_endpoint_with_timeout(self, req):
        req.get.return_value = _FakeResponse({"ok": True})
        result = client.check_health()
        self.assertEqual(result, {"ok": True})
        req.get.assert_called_once_with("http://127.0.0.1:8000/health", timeout=3)
        req.post.assert_not_called()

    @mock.patch("core.des.client.requests")
    def test_check_trigger_posts_to_trigger_check(self, req):
        req.post.return_value = _FakeResponse({"show": True})
        result = client.check_trigger({"text": "x"})
        self.assertEqual(result, {"show": True})
        req.post.assert_called_once_with(
            "http://127.0.0.1:8000/trigger/check", json={"text": "x"}, timeout=3
        )

    @mock.patch("core.des.client.requests")
    def test_start_interaction_posts_to_interaction_start(self, req):
        req.post.return_value = _FakeResponse({"interaction_id": "iid"})
        result = client.start_interaction({"a": 1})
        self.assertEqual(result, {"interaction_id": "iid"})
        req.post.assert_called_once_with(
            "http://127.0.0.1:8000/interaction/start", json={"a": 1}, timeout=3
        )

    @mock.patch("core.des.client.requests")
    def test_answer_interaction_posts_to_interaction_answer(self, req):
        req.post.return_value = _FakeResponse({"done": True})
        payload = {"interaction_id": "iid", "value": "a"}
        result = client.answer_interaction(payload)
        self.assertEqual(result, {"done": True})
        req.post.assert_called_once_with(
            "http://127.0.0.1:8000/interaction/answer", json=payload, timeout=3
        )

    @mock.patch("core.des.client.requests")
    def test_check_health_fails_closed_on_timeout(self, req):
        req.get.side_effect = requests.exceptions.Timeout()
        self.assertEqual(client.check_health(), {"error": "DES unavailable"})

    @mock.patch("core.des.client.requests")
    def test_check_trigger_fails_closed_to_show_false(self, req):
        req.post.side_effect = requests.exceptions.ConnectionError()
        self.assertEqual(client.check_trigger({"x": 1}), {"show": False})

    @mock.patch("core.des.client.requests")
    def test_start_interaction_fails_closed_on_connection_error(self, req):
        req.post.side_effect = requests.exceptions.ConnectionError()
        self.assertEqual(client.start_interaction({"x": 1}), {"error": "DES unavailable"})

    @mock.patch("core.des.client.requests")
    def test_answer_interaction_fails_closed_on_connection_error(self, req):
        req.post.side_effect = requests.exceptions.ConnectionError()
        self.assertEqual(client.answer_interaction({"x": 1}), {"error": "DES unavailable"})

    @mock.patch("core.des.client.requests")
    def test_check_trigger_fails_closed_when_response_not_json(self, req):
        req.post.return_value = _FakeResponse(json_exc=ValueError("no json"))
        self.assertEqual(client.check_trigger({"x": 1}), {"show": False})

    @mock.patch("core.des.client.requests")
    def test_start_interaction_fails_closed_when_response_not_json(self, req):
        req.post.return_value = _FakeResponse(json_exc=ValueError("no json"))
        self.assertEqual(client.start_interaction({"x": 1}), {"error": "DES unavailable"})


class DESFlowThreadingTests(unittest.TestCase):
    @mock.patch("core.des.service.check_trigger")
    def test_trigger_delegates_to_check_trigger(self, check_trigger):
        check_trigger.return_value = {"show": True}
        result = DESFlow().trigger({"text": "x"})
        self.assertEqual(result, {"show": True})
        check_trigger.assert_called_once_with({"text": "x"})

    @mock.patch("core.des.service.start_interaction")
    def test_start_stores_interaction_id_from_response(self, start_interaction):
        start_interaction.return_value = {"interaction_id": "iid-1", "question": {"id": "q1"}}
        flow = DESFlow()
        result = flow.start({"a": 1})
        self.assertEqual(result, {"interaction_id": "iid-1", "question": {"id": "q1"}})
        self.assertEqual(flow.interaction_id, "iid-1")
        start_interaction.assert_called_once_with({"a": 1})

    @mock.patch("core.des.service.answer_interaction")
    @mock.patch("core.des.service.start_interaction")
    def test_answer_threads_stored_interaction_id(self, start_interaction, answer_interaction):
        start_interaction.return_value = {"interaction_id": "iid-1"}
        answer_interaction.return_value = {"done": True}
        flow = DESFlow()
        flow.start({})
        result = flow.answer({"question_id": "q1", "value": "a"})
        self.assertEqual(result, {"done": True})
        answer_interaction.assert_called_once_with(
            {"interaction_id": "iid-1", "question_id": "q1", "value": "a"}
        )

    @mock.patch("core.des.service.answer_interaction")
    def test_answer_before_start_threads_none_interaction_id(self, answer_interaction):
        answer_interaction.return_value = {"done": True}
        DESFlow().answer({"value": "a"})
        answer_interaction.assert_called_once_with({"interaction_id": None, "value": "a"})

    @mock.patch("core.des.service.start_interaction")
    def test_start_without_interaction_id_leaves_it_none(self, start_interaction):
        start_interaction.return_value = {"error": "DES unavailable"}
        flow = DESFlow()
        result = flow.start({})
        self.assertEqual(result, {"error": "DES unavailable"})
        self.assertIsNone(flow.interaction_id)

    @mock.patch("core.des.service.answer_interaction")
    @mock.patch("core.des.service.start_interaction")
    def test_caller_supplied_interaction_id_overrides_stored(self, start_interaction, answer_interaction):
        # Dict-spread order ({"interaction_id": stored, **answer_payload}) means
        # an interaction_id in the answer payload currently wins.
        start_interaction.return_value = {"interaction_id": "stored"}
        answer_interaction.return_value = {"done": True}
        flow = DESFlow()
        flow.start({})
        flow.answer({"interaction_id": "caller", "value": "a"})
        answer_interaction.assert_called_once_with({"interaction_id": "caller", "value": "a"})


if __name__ == "__main__":
    unittest.main()
