#!/bin/bash

# Fetch X (Twitter) feeds using bird CLI
# Run daily at 6am via cron
# Uses credentials from /home/amak/twitter.token

# Set PATH for cron environment
export PATH="/home/amak/.npm-global/bin:/usr/local/bin:/usr/bin:/bin"

X_USERS=(
    "fundstrat"
    "mikealfred"
    "KobeissiLetter"
    "jvisserlabs"
    #"MelMattison1"
    "TimmerFidelity"
    "NoLimitGains"
    "_Checkmatey_"
    "MarkNewtonCMT"
    #"RyanDetrick"
    "TechCharts"
    "PeterLBrandt"
    "LynAldenContact"
)

OUTPUT_FILE="/home/amak/findamak.github.io/x-feed.json"
TOKEN_FILE="/home/amak/twitter.token"

# Load credentials from token file
if [ ! -f "$TOKEN_FILE" ]; then
    echo "Error: $TOKEN_FILE not found" >&2
    exit 1
fi
source "$TOKEN_FILE"

# Collect tweets to temp files, then combine
cutoff=$(date -d '24 hours ago' +%s 2>/dev/null || date -v-24H +%s 2>/dev/null)
TWEETS_DIR=$(mktemp -d)

idx=0
for user in "${X_USERS[@]}"; do
    echo "Fetching @${user}..." >&2
    
    # Fetch and filter tweets for this user, save to temp file
    result=$(bird user-tweets "@${user}" -n 20 \
        --auth-token "$auth_token" \
        --ct0 "$ct0" \
        --json 2>/dev/null)
    
    # Check for rate limit or errors
    if echo "$result" | grep -q "Rate limit"; then
        echo "  ⚠️ Rate limited, skipping..." >&2
        echo "[]" > "$TWEETS_DIR/$idx.json"
    else
        echo "$result" | jq --arg user "$user" --argjson cutoff "$cutoff" '
            [.[] | 
                # Parse createdAt: "Mon Mar 16 18:37:57 +0000 2026" -> epoch
                (.createdAt | strptime("%a %b %d %H:%M:%S %z %Y") | mktime) as $tweetTime |
                select($tweetTime >= $cutoff) | {
                    user: $user,
                    title: (.text // ""),
                    link: ("https://x.com/" + $user + "/status/" + (.id // "")),
                    pubDate: ($tweetTime | strftime("%Y-%m-%dT%H:%M:%SZ")),
                    pubDateRaw: (.createdAt // "")
                }
            ]
        ' > "$TWEETS_DIR/$idx.json" 2>/dev/null || echo "[]" > "$TWEETS_DIR/$idx.json"
    fi
    
    idx=$((idx + 1))
    sleep 3  # Longer delay to avoid rate limits
done

# Combine all temp files and sort newest-first across all users
jq -s '
  add
  | sort_by((.pubDate | strptime("%Y-%m-%dT%H:%M:%SZ") | mktime))
  | reverse
  | {tweets: ., lastUpdated: "'"$(date -Iseconds)"'"}
' "$TWEETS_DIR"/*.json > "$OUTPUT_FILE" 2>/dev/null || echo '{"tweets":[],"lastUpdated":"'$(date -Iseconds)'"}' > "$OUTPUT_FILE"

# Cleanup
rm -rf "$TWEETS_DIR"

# Count tweets
tweet_count=$(jq '.tweets | length' "$OUTPUT_FILE" 2>/dev/null || echo "0")

echo "✓ X feed updated: $(date)"
echo "  Found $tweet_count tweets"
echo "  Output: $OUTPUT_FILE"

# Commit and push to GitHub
echo "Pushing to GitHub..."
cd /home/amak/findamak.github.io

# Check if there are changes
if ! git diff --quiet x-feed.json; then
    git add x-feed.json
    git commit -m "Update X feed at $(date '+%Y-%m-%d %H:%M')"
    git push
    echo "✓ Pushed to GitHub"
else
    echo "  No changes to commit"
fi
