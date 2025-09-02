#!/usr/bin/env bash
set -eu
# gns3_suspend_pair.sh
GNS3_BASE="http://192.168.122.1:3080/v2"
PROJECT="81600c14-839b-4a47-bca6-8bc92cdd5357"
USER="admin"
PASS="password"
NODE_A="68877ba5-c840-41da-ac14-19f148e111ec"
NODE_B="47d56000-71db-4c11-9e40-3b7df1919cbb"
JQ="$(command -v jq || true)"

echo "Querying GNS3 links for project $PROJECT ..."
LINKS_JSON="$(curl -s -u "$USER:$PASS" "$GNS3_BASE/projects/$PROJECT/links")"

if [ -n "$JQ" ]; then
  # find links where both node IDs appear
  LINK_IDS="$(echo "$LINKS_JSON" | jq -r --arg a "$NODE_A" --arg b "$NODE_B" '
    .[] | select((.nodes[].node_id == $a) and (.nodes[].node_id == $b))
    | (.link_id // .id // .uuid)')"
else
  # fallback: crude grep
  LINK_IDS="$(echo "$LINKS_JSON" | grep -Eo '"node_id"[[:space:]]*:[[:space:]]*"[^"]+"' | grep -B1 "$NODE_A" | grep -A1 "$NODE_B" -B1 || true)"
  # Note: fallback unreliable; install jq for robust behavior
fi

if [ -z "$LINK_IDS" ]; then
  echo "No direct link found connecting $NODE_A and $NODE_B."
  echo "You can either:"
  echo "  - isolate node A (suspend all links touching node A), or"
  echo "  - isolate node B, or"
  echo "  - inspect the links JSON manually: save links.json and examine."
  echo "Saving raw links to links.json for manual inspection..."
  echo "$LINKS_JSON" > links.json
  exit 2
fi

echo "Found link(s):"
echo "$LINK_IDS"

for LID in $LINK_IDS; do
  echo "Suspending link $LID ..."
  curl -s -u "$USER:$PASS" -H "Content-Type: application/json" -X PATCH \
    -d '{"suspend": true}' \
    "$GNS3_BASE/projects/$PROJECT/links/$LID" | jq . || true
  echo " -> suspended $LID"
done

echo "Done. Verify with GET:"
for LID in $LINK_IDS; do
  curl -s -u "$USER:$PASS" "$GNS3_BASE/projects/$PROJECT/links/$LID" | jq .
done

echo "When ready to restore, run the unsuspend script or reverse the PATCH to {\"suspend\":false}"
