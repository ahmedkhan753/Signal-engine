import argparse
import sys
from engine import evaluate_signals
from scenarios import scenarios

def list_scenarios():
    print("Available Scenarios:")
    for name in scenarios.keys():
        print(f"- '{name}'")

def run_all():
    for name, signals in scenarios.items():
        evaluate_signals(name, signals)

def main():
    parser = argparse.ArgumentParser(description="Deterministic Decision Engine Prototype")
    parser.add_argument("--list", action="store_true", help="List available scenarios")
    parser.add_argument("--run", type=str, help="Run a specific scenario by name", metavar="SCENARIO_NAME")
    parser.add_argument("--run-all", action="store_true", help="Run all scenarios")

    args = parser.parse_args()

    if args.list:
        list_scenarios()
    elif args.run:
        scenario_name = args.run
        if scenario_name in scenarios:
            evaluate_signals(scenario_name, scenarios[scenario_name])
        else:
            print(f"Error: Scenario '{scenario_name}' not found.")
            list_scenarios()
            sys.exit(1)
    else:
        # Default behavior: run all
        run_all()

if __name__ == "__main__":
    main()
