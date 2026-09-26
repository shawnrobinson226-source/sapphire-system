"""Web bridge for the Sapphire -> DES -> AXIS tri-system flow.

S4: tri state is isolated per browser tab. A browser login session gets a
random ``tri_principal`` in its signed session cookie; each tab obtains a
server-minted tab token (POST /api/tri/tab-token) bound to that principal and
sends it as ``X-Tri-Tab-Token``. TriBridgeRegistry maps tab token -> per-tab
bridge. A token is honored only for the session whose principal it is bound
to; API-key callers never reach a tri flow.

Tokens, principals and operator IDs are never logged or returned (other than
the token endpoint's own response).
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from core.des.tri_system_flow import PENDING_EXECUTION_TTL_SECONDS, TriSystemFlow
from core.identity.operator import resolve_operator_id
from ui.views import render_tri_state


TRI_START_TRIGGERS = {"tri", "/tri"}
TRI_CONFIRM_COMMAND = "confirm"
TRI_REJECT_COMMANDS = {"reject", "cancel"}

TRI_TAB_TOKEN_HEADER = "X-Tri-Tab-Token"
TRI_PRINCIPAL_SESSION_KEY = "tri_principal"
MAX_TRI_TABS = 256
TRI_TAB_IDLE_SECONDS = PENDING_EXECUTION_TTL_SECONDS

TRI_TAB_INVALID_MESSAGE = (
    "Tri-System is not available for this tab (missing or expired tab session).\n"
    "Type tri to start again."
)
TRI_API_KEY_DENIED_MESSAGE = "Tri-System actions require a signed-in browser session."
TRI_CAPACITY_MESSAGE = "Tri-System is at capacity. Try again later."


def resolve_web_operator_id(prompt: bool = False) -> str | None:
    return resolve_operator_id(prompt=False)


def make_web_tri_system_flow() -> TriSystemFlow:
    return TriSystemFlow(identity_resolver=resolve_web_operator_id)


class WebTriSystemBridge:
    """Drive one tab's TriSystemFlow from chat text without involving the LLM/tool path."""

    def __init__(self, flow_factory: Callable[[], TriSystemFlow] = make_web_tri_system_flow):
        self.flow_factory = flow_factory
        self.flow: TriSystemFlow | None = None
        self.active = False
        # Guards bridge state. Held for start/answer/reject; for confirm only
        # while the pending execution is claimed, never during the dispatch.
        self.lock = threading.Lock()

    def handle(self, text: str) -> str | None:
        command = self._normalize(text)
        with self.lock:
            if not self.active:
                if command not in TRI_START_TRIGGERS:
                    return None
                self.flow = self.flow_factory()
                self.active = True
                return self._render_terminal_if_needed(self.flow.start())

            if self.flow is None:
                self.active = False
                return None

            if self._awaiting_confirmation():
                if command == TRI_CONFIRM_COMMAND:
                    flow = self._claim_confirmation()
                    if flow is None:
                        return None
                elif command in TRI_REJECT_COMMANDS:
                    state = self.flow.cancel()
                    self.active = False
                    return render_tri_state(state)
                else:
                    return (
                        "Tri-System confirmation pending.\n"
                        "Type confirm to execute AXIS, or reject to cancel."
                    )
            else:
                state = self.flow.submit_answer(text)
                if state.get("type") == "result":
                    return self._render_result_preview_confirm(state)
                return self._render_terminal_if_needed(state)

        # Dispatch outside the lock: the claim above already made this the
        # only confirm that can reach the flow's pending execution.
        return render_tri_state(flow.confirm())

    def _claim_confirmation(self) -> TriSystemFlow | None:
        """Atomically take the pending execution (caller holds self.lock)."""
        flow = self.flow
        if flow is None or flow.pending_execution is None or flow.axis_attempted:
            return None
        self.active = False
        return flow

    def has_live_pending(self) -> bool:
        """True while busy or holding an unexpired pending execution (flow TTL is wall-clock)."""
        if self.lock.locked():
            return True
        flow = self.flow
        pending = getattr(flow, "pending_execution", None) if flow is not None else None
        if not isinstance(pending, dict):
            return False
        return pending.get("expires_at", 0) > time.time()

    def _render_result_preview_confirm(self, state: dict) -> str:
        if self.flow is None:
            return render_tri_state(state)
        preview = self.flow.axis_preview()
        confirm = self.flow.confirm_state()
        return "\n\n".join(
            part
            for part in [
                render_tri_state(state),
                render_tri_state(preview),
                render_tri_state(confirm),
            ]
            if part
        )

    def _render_terminal_if_needed(self, state: dict) -> str:
        if state.get("type") in {"error", "idle", "axis_result"}:
            self.active = False
        return render_tri_state(state)

    def _awaiting_confirmation(self) -> bool:
        if self.flow is None:
            return False
        return self.flow.question is None and self.flow.pending_execution is not None

    @staticmethod
    def _normalize(text: str) -> str:
        return (text or "").strip().lower()


@dataclass
class _TabEntry:
    principal: str
    created_at: float
    last_seen: float
    bridge: WebTriSystemBridge = field(repr=False)

    def __repr__(self) -> str:  # never expose the principal
        return "_TabEntry(<redacted>)"


@dataclass(frozen=True)
class TriResult:
    """Outcome of routing one chat message: text to show (None -> normal chat)."""

    text: str | None
    token_invalid: bool = False


class TriBridgeRegistry:
    """Bounded tab token -> per-tab bridge map with idle expiry."""

    def __init__(
        self,
        flow_factory: Callable[[], TriSystemFlow] = make_web_tri_system_flow,
        *,
        max_tabs: int = MAX_TRI_TABS,
        idle_seconds: float = TRI_TAB_IDLE_SECONDS,
        clock: Callable[[], float] = time.time,
    ):
        self.flow_factory = flow_factory
        self.max_tabs = max_tabs
        self.idle_seconds = idle_seconds
        self.clock = clock
        self._entries: dict[str, _TabEntry] = {}
        self._lock = threading.Lock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    # ---- issuance ----

    @staticmethod
    def ensure_principal(session: Any) -> str:
        """Return the session's tri principal, minting a random one if absent."""
        principal = session.get(TRI_PRINCIPAL_SESSION_KEY)
        if not isinstance(principal, str) or not principal:
            principal = secrets.token_urlsafe(32)
            session[TRI_PRINCIPAL_SESSION_KEY] = principal
        return principal

    def issue_token(self, principal: str) -> str | None:
        """Register a new tab token bound to ``principal``; None when full of live tabs."""
        now = self.clock()
        with self._lock:
            self._purge_idle(now)
            if len(self._entries) >= self.max_tabs and not self._evict_one():
                return None
            token = secrets.token_urlsafe(32)
            self._entries[token] = _TabEntry(
                principal=principal,
                created_at=now,
                last_seen=now,
                bridge=WebTriSystemBridge(flow_factory=self.flow_factory),
            )
            return token

    def _is_idle(self, entry: _TabEntry, now: float) -> bool:
        return now - entry.last_seen >= self.idle_seconds and not entry.bridge.has_live_pending()

    def _purge_idle(self, now: float) -> None:
        for token in [t for t, e in self._entries.items() if self._is_idle(e, now)]:
            del self._entries[token]

    def _evict_one(self) -> bool:
        """Evict the least recently used entry without a live pending execution."""
        candidates = [(e.last_seen, t) for t, e in self._entries.items() if not e.bridge.has_live_pending()]
        if not candidates:
            return False
        del self._entries[min(candidates)[1]]
        return True

    # ---- lookup ----

    def _lookup(self, token: Any, principal: Any) -> WebTriSystemBridge | None:
        if not isinstance(token, str) or not token or not isinstance(principal, str) or not principal:
            return None
        now = self.clock()
        with self._lock:
            entry = self._entries.get(token)
            if entry is None:
                return None
            if not secrets.compare_digest(entry.principal, principal):
                return None
            if self._is_idle(entry, now):
                del self._entries[token]
                return None
            entry.last_seen = now
            return entry.bridge

    # ---- routing ----

    def handle(self, text: str, *, tab_token: Any, principal: Any, browser_session: bool) -> TriResult:
        command = WebTriSystemBridge._normalize(text)
        if not browser_session:
            if command in TRI_START_TRIGGERS:
                return TriResult(TRI_API_KEY_DENIED_MESSAGE)
            return TriResult(None)
        bridge = self._lookup(tab_token, principal)
        if bridge is None:
            if command in TRI_START_TRIGGERS:
                return TriResult(TRI_TAB_INVALID_MESSAGE, token_invalid=True)
            return TriResult(None)
        return TriResult(bridge.handle(text))

    def handle_request(self, request: Any, text: str) -> TriResult:
        """Route one chat message using the request's session and headers."""
        headers = request.headers
        session = request.session
        browser_session = bool(session.get("logged_in")) and not headers.get("X-API-Key")
        return self.handle(
            text,
            tab_token=headers.get(TRI_TAB_TOKEN_HEADER),
            principal=session.get(TRI_PRINCIPAL_SESSION_KEY),
            browser_session=browser_session,
        )


_WEB_TRI_REGISTRY = TriBridgeRegistry()


def get_web_tri_registry() -> TriBridgeRegistry:
    return _WEB_TRI_REGISTRY
