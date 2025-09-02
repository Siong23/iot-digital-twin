#!/usr/bin/env bash
set -euo pipefail

# gns3_suspend_pair.sh - find links connecting NODE_A <-> NODE_B and suspend them

# --- CONFIG (edit if needed) ---
GNS3_BASE="${GNS3_BASE:-http://192.168.122.1:3080/v2}"
PROJECT="${PROJECT:-81600c14-839b-4a47-bca6-8bc92cdd5357}"
USER="${USER:-admin}"
PASS="${PASS:-password}"
NODE_A="${NODE_A:-68877ba5-c840-41da-ac14-19f148e111ec}"   # sensor node id
NODE_B="${NODE_B:-47d56000-71db-4c11-9e40-3b7df1919cbb}"   # broker node id

# --- helpers ---
command -v curl >/dev/null 2>&1 || { echo "curl not found, install curl"; exit 2; }
if ! command -v jq >/dev/null 2>&1; then
  echo "jq not found. Please install jq (apt install jq) for reliable JSON parsing."
  exit 2
fi

echo "Querying GNS3 links for project $PROJECT ..."
API="$GNS3_BASE/projects/$PROJECT/links"
# fetch links and check HTTP status
HTTP_OUT="$(mktemp)"
HTTP_CODE="$(curl -sS -u "$USER:$PASS" -o "$HTTP_OUT" -w "%{http_code}" "$API")"
if [[ "$HTTP_CODE" != "200" ]]; then
  echo "Failed to fetch links (HTTP $HTTP_CODE). Response:"
  sed -n '1,200p' "$HTTP_OUT"
  rm -f "$HTTP_OUT"
  exit 3
fi

LINKS_JSON="$(cat "$HTTP_OUT")"
rm -f "$HTTP_OUT"

# find links where both node ids appear (robust to link_id/id/uuid naming)
LINK_IDS="$(echo "$LINKS_JSON" | jq -r --arg a "$NODE_A" --arg b "$NODE_B" '
  .[] | select((.nodes[].node_id == $a) and (.nodes[].node_id == $b))
     | (.link_id // .id // .uuid // "") | select(. != "")')"

if [[ -z "$LINK_IDS" ]]; then
  echo "No direct link found connecting $NODE_A and $NODE_B."
  echo "Saved raw links to links.json for inspection."
  printf '%s\n' "$LINKS_JSON" > links.json
  echo "Consider isolating one of the nodes instead (see gns3_isolate_node.sh)."
  exit 4
fi

echo "Found link(s) connecting the nodes:"
echo "$LINK_IDS"
for LID in $LINK_IDS; do
  echo "Suspending link $LID ..."
  PATCH_API="$GNS3_BASE/projects/$PROJECT/links/$LID"
  # send PATCH with JSON and show response
  curl -sS -u "$USER:$PASS" -H "Content-Type: application/json" -X PATCH \
    -d '{"suspend": true}' \
    "$PATCH_API" | jq .
  echo " -> suspended $LID"
done

echo "Done. You can verify with:"
echo "curl -s -u $USER:<PASS> \"$GNS3_BASE/projects/$PROJECT/links/<link_id>\" | jq ."
echo "To unsuspend, run the same PATCH with '{\"suspend\": false}'."

