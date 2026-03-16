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
    "MelMattison1"
    "NoLimitGains"
    "_Checkmatey_"
    "MarkNewtonCMT"
    "RyanDetrick"
    "MarioNawfal"
)

OUTPUT_FILE="/home/amak/findamak.github.io/x-feed.json"
TOKEN_FILE="/home/amak/twitter.token"

# Load credentials from token file
if [ ! -f "$TOKEN_FILE" ]; then
    echo "Error: $TOKEN_FILE not found" >&2
    exit 1
fi
source "$TOKEN_FILE"

# Build JSON using jq
all_tweets="[]"

for user in "${X_USERS[@]}"; do
    echo "Fetching @${user}..." >&2
    
    # Fetch tweets (50 per user to avoid rate limits, should cover 24h for most accounts)
    tweets=$(bird user-tweets "@${user}" -n 50 \
        --auth-token "$auth_token" \
        --ct0 "$ct0" \
        --json 2>/dev/null)
    
    if [ -z "$tweets" ] || [ "$tweets" = "[]" ]; then
        echo "  No tweets found for $user" >&2
        continue
    fi
    
    # Filter to last 24 hours and transform
    cutoff=$(date -d '24 hours ago' -Iseconds 2>/dev/null || date -v-24H -Iseconds 2>/dev/null)
    user_tweets=$(echo "$tweets" | jq --arg user "$user" --arg cutoff "$cutoff" '
        .tweets // [] | [.[] | select((.createdAt // "") >= $cutoff) | {
            user: $user,
            title: (.text // ""),
            link: ("https://x.com/" + $user + "/status/" + (.id // "")),
            pubDate: (.createdAt // "")
        }]
    ')
    
    # Append to all_tweets
    all_tweets=$(echo "$all_tweets" "$user_tweets" | jq -s 'add')
    
    sleep 2
done

# Create final JSON with timestamp
jq -n --argjson tweets "$all_tweets" --arg updated "$(date -Iseconds)" '{
    tweets: $tweets,
    lastUpdated: $updated
}' > "$OUTPUT_FILE"

echo "✓ X feed updated: $(date)"
echo "  Found $(echo "$all_tweets" | jq 'length') tweets"
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
