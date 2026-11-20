#!/usr/bin/env bash
set -euo pipefail
[ ! -d '/agent/repos/action-items' ] || cd '/agent/repos/action-items' || exit $?
pip3 install --user -r requirements.txt