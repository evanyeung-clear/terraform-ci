#!/usr/bin/env bash
# Rewrites SARIF artifact URIs to be relative to repo root.
# GitHub does not respect uriBaseId, so this resolves each uri by prepending
# the base path from originalUriBaseIds and making it relative to the repo root.
#
# Usage: ./rewrite-sarif-uris.sh <sarif-file> [repo-root]
#   sarif-file  Path to the SARIF file to rewrite (modified in place)
#   repo-root   Repo root path (default: git rev-parse --show-toplevel)

set -euo pipefail

INPUT="${1:?Usage: $0 <sarif-file> [repo-root]}"

if [[ ! -f "$INPUT" ]]; then
  echo "Error: file not found: $INPUT" >&2
  exit 1
fi

if ! command -v jq &>/dev/null; then
  echo "Error: jq is required but not installed" >&2
  exit 1
fi

# Resolve repo root: prefer arg, then git, then directory of the input file
if [[ -n "${2:-}" ]]; then
  REPO_ROOT="$2"
else
  REPO_ROOT="$(git -C "$(dirname "$(realpath "$INPUT")")" rev-parse --show-toplevel 2>/dev/null || dirname "$(realpath "$INPUT")")"
fi

# Normalize: no trailing slash
REPO_ROOT="${REPO_ROOT%/}"

REWRITTEN="$(jq --arg repo_root "$REPO_ROOT" '
  .runs |= map(
    (.originalUriBaseIds // {}) as $bases |
    .results |= map(
      .locations |= map(
        if .physicalLocation.artifactLocation.uriBaseId != null then
          (.physicalLocation.artifactLocation.uriBaseId) as $id |
          if $bases[$id] != null then
            ($bases[$id].uri | ltrimstr("file://")) as $base_path |
            # Make base_path relative to repo root (strip leading repo_root prefix)
            (if ($base_path | startswith($repo_root + "/"))
             then $base_path | ltrimstr($repo_root + "/")
             else $base_path | ltrimstr("/")
             end) as $rel_base |
            .physicalLocation.artifactLocation |= {
              "uri": ($rel_base + .uri)
            }
          else . end
        else . end
      )
    )
  )
' "$INPUT")"

echo "$REWRITTEN" > "$INPUT"
echo "Rewrote URIs in $INPUT (repo root: $REPO_ROOT)"
