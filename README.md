# Deterministic Decision Engine Prototype

A lightweight, purely deterministic Python prototype designed to evaluate incoming system signals, detect conflicts, calculate alignment scores, and emit an automated decision (ALLOW, DELAY, or BLOCK).

## 🎯 What We Built

We created a transparent, rule-based decision engine designed to operate without any black-box logic (no LLMs, no external APIs). The core focus is on **Clarity, Simplicity, and Determinism**.

### Key Features:
1. **Signal Processing**: Ingests multiple named system signals (e.g., `system_stability`, `error_rate`) with risk values of `HIGH`, `MEDIUM`, or `LOW`.
2. **Conflict Detection**: Automatically identifies conflicting or contradictory signals (e.g., reporting a `HIGH` error rate alongside `HIGH` system stability).
3. **Alignment Scoring (0–100)**: 
   - Starts at a perfect 100.
   - Deducts points based on the severity of negative signals (e.g., a `HIGH` security threat results in a -15 penalty).
   - Deducts an additional penalty (-8) when logical conflicts are detected.
4. **Deterministic Decisions**:
   - **70–100**: ALLOW
   - **40–69**: DELAY
   - **0–39**: BLOCK
5. **Auditable Trace Output**: Generates a clear, human-readable trace explaining *exactly* why a decision was reached and how the score was calculated.

---

## 🚀 How to Test it End-to-End

To demonstrate the engine's capabilities to the client, you can run the pre-built scenarios via the Command Line Interface (CLI).

### 1. Prerequisites
Ensure you have Python 3.x installed on your machine. There are no external dependencies or virtual environments required.

### 2. Run All Scenarios
To run all test scenarios sequentially and view their traces, open your terminal in the project directory and run:

```bash
python main.py --run-all
```
*(Note: Running `python main.py` without arguments also runs all scenarios by default).*

### 3. Run a Specific Scenario
You can test a specific scenario by passing its exact name:

```bash
python main.py --run "Conflicting Signals"
```

To see a list of available scenarios:
```bash
python main.py --list
```

---

## 🧪 Scenarios Included for Demonstration

We have prepared three distinct scenarios to showcase the engine's behavior:

1. **"All Good"** 
   - **Expected Outcome:** `ALLOW` (Score: 100/100)
   - **Why:** All system vitals are healthy. No penalties are applied.

2. **"Conflicting Signals"**
   - **Expected Outcome:** `DELAY` (Score: 69/100)
   - **Why:** Simulates an environment where `system_stability` is HIGH, but `error_rate` is also HIGH. The engine correctly identifies this contradiction, applies base penalties for the elevated error rate, and applies a conflict penalty, resulting in a delayed action.

3. **"Critical Failure"**
   - **Expected Outcome:** `BLOCK` (Score: 30/100)
   - **Why:** Multiple critical negative signals (high error rate, high deployment risk, high security threat, and high data loss risk) accumulate massive penalties, dropping the alignment score below the threshold required to proceed.

---

## 📁 Project Structure
- `engine.py` - Contains the core scoring, conflict detection, and trace generation logic.
- `scenarios.py` - Stores the signal dictionaries used for testing.
- `main.py` - The CLI entry point for running the demonstration.
