#!/bin/bash
set -euo pipefail

APP_DIR="${APP_DIR:-/home/botuser/app}"

shopt -s nullglob
for profile_setup in "$APP_DIR"/instance/*/setup.sh; do
    echo "Running profile build hook: ${profile_setup#"$APP_DIR"/}"
    bash "$profile_setup"
done

echo "Runner image setup complete"
