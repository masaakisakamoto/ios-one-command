#!/bin/bash
set -euo pipefail
tool_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$tool_root"
python3 -m unittest discover -s tests
exec /bin/bash "$tool_root/ios-one" verify --project "$tool_root/examples/HelloDevice/HelloDevice.xcodeproj" --scheme HelloDevice --no-input --lang ja "$@"
