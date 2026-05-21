import re

ZERO_TOOLS_INSTRUCTION = (
    "No tools are available in this mode. Do not claim tool access. "
    "Do not offer to execute tools."
)
ZERO_TOOLS_BLOCKED_NAMES = ("execute_axis", "list_tools")
ZERO_TOOLS_PROMPT_PATTERNS = (
    r"\btools?\b",
    r"\btoolsets?\b",
    r"\bfunction calling\b",
    r"\bweb search\b",
    r"\bpersistent memory\b",
    r"\bmodify your own prompt\b",
    r"\bexecute_axis\b",
    r"\blist_tools\b",
)


def is_explicit_zero_tools_request(text: str) -> bool:
    lowered = (text or "").lower()
    return any(name in lowered for name in ZERO_TOOLS_BLOCKED_NAMES)


def zero_tools_unavailable_response() -> str:
    return "No tools are available in this mode. I cannot list, call, or execute tools."


def strip_tool_affordances_from_prompt(prompt: str) -> str:
    clean_lines = []
    for line in (prompt or "").splitlines():
        lowered = line.lower()
        if any(re.search(pattern, lowered) for pattern in ZERO_TOOLS_PROMPT_PATTERNS):
            continue
        clean_lines.append(line)
    return "\n".join(clean_lines).strip()
