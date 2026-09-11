#!/bin/bash
set -euo pipefail
tool_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
exec python3 "$tool_root/scripts/publish.py" "$@"
