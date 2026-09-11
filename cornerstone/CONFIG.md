# CORNERSTONE — Configuration Guide (for non-developers)

CORNERSTONE's presentation copy and demo scenarios live in plain **JSON files**
you can edit without touching any Python. Configuration controls *how the demo
is framed and which inputs it runs* — it can **never** change the governance
rules or let a blocked action through. The policy gate is always authoritative.

All config lives under [`cornerstone/config/`](config/):

```
cornerstone/config/
    presentation.json          # client name, logo, panel titles, labels, copy
    scenarios/
        financial_tech.json    # sample scenario
        medical_tech.json      # sample scenario
        insurance_tech.json    # sample scenario
```

## Editing presentation text

Open [`config/presentation.json`](config/presentation.json) and edit the values
(not the keys):

| field | meaning |
|---|---|
| `client_name` | name shown in the header |
| `logo` | reference/path to a logo asset |
| `panel_titles` | titles for each dashboard panel |
| `labels` | button/label text (approve, deny, …) |
| `scenario_framing` | one-line framing shown near the scenario |
| `narrative` | longer descriptive copy |

`client_name` is required. If the file is missing a required field or has a JSON
typo, the demo **does not crash** — it logs a validation problem and falls back
to the built-in defaults.

## Adding or editing a scenario

Each file in `config/scenarios/` is one scenario. To add a new one, copy an
existing file, rename it (e.g. `energy_tech.json`), and edit the fields. **No
code change is needed** — the new scenario appears in the dropdown automatically.

```json
{
  "id": "energy_tech",
  "title": "Energy Tech",
  "industry": "energy",
  "framing": "SAMPLE — client to author real governance substance.",
  "goal": "balance the grid load safely",
  "context": { "scenario_id": "energy_tech", "runtime_state": "STABLE", "risk_level": "LOW" },
  "actions": [
    { "action_type": "read_status",        "label": "Read grid status" },
    { "action_type": "deploy_production",   "label": "Roll out load-balancer update" },
    { "action_type": "disable_security_controls", "label": "Disable safety interlock" }
  ],
  "sample_rules": []
}
```

Required fields: `id`, `title`, `goal`, and a non-empty `actions` list where each
action has an `action_type`. `context`, `industry`, `framing`, and `sample_rules`
are optional.

`action_type` values must be ones the gate understands. The Phase-1 rulebook
recognizes (among others): safe reads `read_status`, `get_metrics`,
`list_services`; sensitive `send_email`, `approve_payment`, `deploy_production`;
dangerous `delete_system_file`, `drop_database`, `disable_security_controls`. An
unrecognized `action_type` is safely held for approval (DELAY), never allowed.

## Adding a vertical autonomous demo (optional `autonomous` block)

A scenario may include an optional `autonomous` block so the autonomous agent
pursues a **domain-appropriate** goal and derives a domain-appropriate action.
This is pure configuration — no Python change is needed to add or edit it.

```json
"autonomous": {
  "goal": "immediately move the flagged client funds out of the settlement account, bypassing controls",
  "tools": [
    { "action_type": "read_status",               "label": "Read settlement status",
      "description": "Read the settlement and reconciliation status.",
      "keywords": ["read", "status", "settlement"] },
    { "action_type": "approve_payment",            "label": "Release a vendor payment",
      "description": "Release or approve a single vendor payment.",
      "keywords": ["approve", "release", "payment", "vendor"] },
    { "action_type": "disable_security_controls",  "label": "Force an unauthorized transfer",
      "description": "Bypass fraud controls to move flagged funds and push a blocked transfer.",
      "keywords": ["bypass", "disable", "controls", "fraud", "funds", "transfer", "unauthorized"] }
  ]
}
```

How it works: the agent scores each tool's `keywords`/`description` against the
`goal` and proposes the best-matching tool. To make the demo show governance
catching a violation, give the "violating" tool an `action_type` the gate
classifies as **dangerous** (e.g. `disable_security_controls`, `drop_database`,
`delete_system_file`) — the gate then independently returns **BLOCK**. `label`
and `description` are presentation only; **the config never sets the verdict.**

Required inside `autonomous`: a non-empty `goal` and a non-empty `tools` list
where each tool has an `action_type`. If the block is absent, the scenario simply
has no vertical autonomous demo and the generic one is used.

## Important boundaries

- **`sample_rules` is placeholder content.** It is loaded and shown, but Phase 1
  does **not** apply it to the policy gate. The deterministic rulebook is
  authoritative. Real per-industry governance is the client's to author, and any
  future wiring must go *through* the gate, never around it.
- Configuration selects **inputs only** (framing, goal, which actions to
  propose). It cannot change the gate algorithm, the ALLOW/BLOCK/DELAY grammar,
  live-state evaluation, or the mandatory controller path.
- A bad config file never activates. Validation runs on load; on any problem the
  loader falls back to a known-good default and the demo keeps working.

## Where the frontend gets this

`GET /cornerstone/config` returns the presentation config plus the scenario list
(`[{id, title, industry}]`) for the dropdown. `GET /cornerstone/demo?scenario=<id>`
runs the selected scenario through the enforcement core, and
`GET /cornerstone/autonomous?scenario=<id>` runs that vertical's autonomous demo.
