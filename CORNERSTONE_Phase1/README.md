# CORNERSTONE Phase 1 — Client Delivery Package

Welcome to the client delivery handoff package for **CORNERSTONE Phase 1**.

CORNERSTONE is a **runtime governance-control layer** designed to sit in front of system action execution. While the VECTOR decision engine suggests actions, CORNERSTONE governs whether and how those actions are carried out. It implements a structured evaluation loop featuring an automated policy gate, a human approval queue runtime, an append-only ledger, and stable serialization contracts.

> [!NOTE]
> This package is entirely **additive** and does not modify the core VECTOR V2/V3 codebases.
> It introduces a dedicated control boundary for action governance, exposing it via a clean Flask API blueprint.

---

## 📁 Folder Structure

The delivery package is organized as follows:

```text
CORNERSTONE_Phase1/
├── README.md                # This project guide and setup documentation
├── requirements.txt         # Minimal Python project dependencies (Flask)
├── CONTRACTS.md             # Section 7 stable frontend/dashboard wire formats
├── API.md                   # HTTP endpoints and Flask Blueprint routing documentation
├── PHASE1_ACCEPTANCE.md     # Acceptance criteria mapping and verification report
├── demo_runner.py           # Root wrapper script to run the interactive demo
└── cornerstone/             # Core Python package containing source and tests
    ├── __init__.py          # Package exports
    ├── acceptance.py        # Programmatic acceptance validator
    ├── agent.py             # Scripted Agent simulating demo execution
    ├── api.py               # Flask Blueprint exposing endpoints
    ├── contracts.py         # JSON serialization contract builders
    ├── controller.py        # Central runtime governance orchestrator
    ├── executor.py          # Simulated action executor
    ├── ledger.py            # Append-only in-memory workflow ledger
    ├── models.py            # Shared data models and type definitions
    ├── policy_gate.py       # Core PolicyGate rule evaluation engine
    ├── policy_rules.py      # Declarative rulebook definitions
    ├── queue_manager.py     # Under-the-hood human-in-the-loop queue
    ├── workflow.py          # Workflow structure initializer
    └── test_*.py            # Automated test suite (93 test cases)
```

---

## 🚀 Installation & Prerequisites

### Prerequisites
- Python 3.8 or newer.
- No database or external services are needed. Everything runs in-memory for this milestone.

### Installation
To install the minimal dependencies required (primarily Flask for the API layer), execute the following command from the root of the extracted package directory:

```bash
pip install -r requirements.txt
```

---

## 💻 Running the Demo

To demonstrate the full execution and enforcement loop (Agent ➔ Controller ➔ Policy Gate ➔ Executor/Queue) end-to-end, execute the interactive `demo_runner.py`:

```bash
python demo_runner.py
```

### What to Expect:
1. **Step 1 (read_status):** Evaluates to `ALLOW` based on safety rules and executes immediately.
2. **Step 2 (send_email):** Evaluates to `DELAY` (sensitive action). It enters the `QueueManager` as a pending approval. The demo simulates a human `APPROVE` verdict, causing it to resume and execute.
3. **Step 3 (delete_system_file):** Evaluates to `BLOCK` (dangerous action) and is rejected immediately.
4. **Deny Path Demo:** Simulates a fresh workflow where a sensitive action is `DELAY`'d and then rejected (`DENY`) by the operator, showing it is correctly killed.
5. **Acceptance Validator:** The runner automatically validates all Phase 1 criteria (ledger consistency, exactly-once semantics, state validation) and outputs `PASS`.

---

## 🧪 Running the Tests

To verify that the complete suite of **93 automated tests** passes successfully on your system:

```bash
python -m unittest discover -s cornerstone -p "test_*.py"
```

The test suite covers:
- **Contract Schema compliance** (verifying output matches Section 7 JSON shapes precisely).
- **Rule evaluation** (policy gate rules, matching correctness).
- **Controller & Executor runtime** (exactly-once execution, deferred queues).
- **Blueprint API validation** (client routing, demo workflows, validation error handling).

---

## 📊 Dashboard Team Integration

> [!IMPORTANT]
> The frontend and dashboard teams should refer directly to:
> - **[CONTRACTS.md](CONTRACTS.md)**: Defines the exact JSON models to build the UI against (Decision Record, Pending Approval, Run Summary, Trace Entry).
> - **[API.md](API.md)**: Details the HTTP endpoints (routes, payloads, and response shapes) exposed by the Flask Blueprint.
