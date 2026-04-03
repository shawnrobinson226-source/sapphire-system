VALID_URGENCIES = {"low", "normal", "high"}
VALID_TASK_STATES = {"pending", "active", "blocked", "complete", "cancelled"}
VALID_STEP_STATUSES = {"pending", "active", "complete", "blocked"}
VALID_ROUTES = {"builder", "researcher", "operator", "editor"}
VALID_TASK_TYPES = {"build", "research", "operate", "edit", "setup", "general"}

TASK_TYPE_TO_ROUTE = {
    "build": "builder",
    "research": "researcher",
    "operate": "operator",
    "setup": "operator",
    "edit": "editor",
    "general": "operator",
}

CLASSIFY_PATTERNS = [
    ("setup", ["set up", "setup", "configure", "initialize", "install"]),
    ("build", ["build", "create", "make", "code", "develop"]),
    ("research", ["research", "find", "compare", "analyze", "investigate"]),
    ("operate", ["run", "execute", "fix"]),
    ("edit", ["rewrite", "edit", "improve", "refine", "clean up"]),
]

BUILDER_STEPS = [
    "Define deliverable",
    "Create file or structure outline",
    "Implement core logic",
    "Test minimal version",
    "Record next upgrade",
]

RESEARCHER_STEPS = [
    "Clarify question",
    "Gather relevant inputs",
    "Compare findings",
    "Extract key signal",
    "Return concise recommendation",
]

OPERATOR_STEPS = [
    "Identify current state",
    "Verify required dependency or condition",
    "Perform next setup/action step",
    "Test result",
    "Record blocker or next move",
]

EDITOR_STEPS = [
    "Review source material",
    "Identify weak sections",
    "Tighten structure",
    "Improve clarity",
    "Return revised output",
]
