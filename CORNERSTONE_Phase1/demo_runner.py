"""
CORNERSTONE Phase 1 — client delivery demo runner wrapper.
Exposes the demo execution directly from the root of the handoff package.
"""

import sys
from cornerstone.demo_runner import run

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
