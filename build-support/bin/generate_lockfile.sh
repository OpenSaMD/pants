#!/usr/bin/env bash

set -euo pipefail

constraints_file=3rdparty/python/constraints.txt

VENV=$(mktemp -d -t pants_lockfile_venv.XXXXX)
python3 -m venv "${VENV}"
"${VENV}/bin/pip" install -r <(./pants --tag=-lockfile_ignore dependencies --type=3rdparty ::)
echo "# Generated by build-support/bin/generate_lockfile.sh on $(date)" > "${constraints_file}"
"${VENV}/bin/pip" freeze --all >> "${constraints_file}"
