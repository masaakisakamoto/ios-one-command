#!/usr/bin/env python3
"""Mac-only smoke check: build, install and launch the bundled demo in Simulator."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ios_one.cli import simulator_targets, version


def main():
    output = subprocess.check_output(["/usr/bin/xcrun", "simctl", "list", "devices", "available", "-j"], text=True)
    targets = [t for t in simulator_targets(json.loads(output)) if t.name.startswith("iPhone")]
    if not targets:
        sys.exit("No iOS 17+ iPhone Simulator runtime installed. Add one in Xcode Settings > Components.")
    targets.sort(key=lambda t: (t.state != "Booted", tuple(-v for v in version(t.os_version)), t.name, t.identifier))
    target = targets[0]
    print("Simulator smoke target: " + target.name + " / " + target.os_version, flush=True)
    return subprocess.call(["/bin/bash", str(ROOT / "ios-one"), "demo", "--simulator", target.identifier, "--no-input", "--lang", "en"])


if __name__ == "__main__":
    sys.exit(main())
