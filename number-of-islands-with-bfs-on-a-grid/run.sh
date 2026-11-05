#!/usr/bin/env bash
# Replays the terminal demo from the short in the same container image.
# Needs Docker. Run from anywhere: ./run.sh
set -euo pipefail
cd "$(dirname "$0")"

docker run --rm -i -v "$(pwd -P)":/work -w /work python:3.12-slim \
  sh -c 'if command -v bash >/dev/null 2>&1; then exec bash -s; else exec sh -s; fi' <<'STUDIO_EOF'
python3 islands.py
STUDIO_EOF
