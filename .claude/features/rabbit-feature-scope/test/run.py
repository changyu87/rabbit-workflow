#!/usr/bin/env python3

import subprocess
import sys
from pathlib import Path

script_dir = Path(__file__).parent
PASS = 0
FAIL = 0

for t in sorted(script_dir.glob("test-*.py")):
    result = subprocess.run([sys.executable, str(t)])
    if result.returncode == 0:
        PASS += 1
    else:
        FAIL += 1

print(f"Total: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
