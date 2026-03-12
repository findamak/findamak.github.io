#!/bin/bash

# Fetch X (Twitter) feeds using RSS from x.g0blin.sh (RSS Bridge)
# Run daily at 6am via cron

X_USERS=(
    "fundstrat"
    "mikealfred"
    "KobeissiLetter"
    "jvisserlabs"
    "MelMattison1"
    "NoLimitGains"
)

OUTPUT_FILE="/home/amak/findamak.github.io/x-feed.json"
TEMP_FILE=$(mktemp)

# Initialize tweets array
echo '{"tweets": [' > "$TEMP_FILE"

first=true

for user in "${X_USERS[@]}"; do
    # Try RSS Bridge instance
    rss_url="https://x.g0blin.sh/bridge/?action=display&bridge=Twitter&u=${user}&format=Atom"
    
    echo "Fetching @${user}..." >&2
    
    # Fetch with timeout
    rss_content=$(curl -s --max-time 20 -A "Mozilla/5.0" "$rss_url")
    
    if [ -z "$rss_content" ]; then
        echo "  Failed to fetch feed for $user" >&2
        continue
    fi
    
    # Extract entries (limit to 5 per user)
    echo "$rss_content" | grep -oP '<entry>.*?</entry>' | head -5 | while IFS= read -r entry; do
        # Extract title (remove HTML tags)
        title=$(echo "$entry" | grep -oP '(?<=<title>)[^<]+' | head -1 | sed 's/<[^>]*>//g' | head -c 280)
        
        # Extract link
        link=$(echo "$entry" | grep -oP '(?<=<link rel="alternate" href=")[^"]+' | head -1)
        if [ -z "$link" ]; then
            link=$(echo "$entry" | grep -oP '(?<=<link>)[^<]+' | head -1)
        fi
        
        # Extract published date
        pubdate=$(echo "$entry" | grep -oP '(?<=<published>)[^<]+' | head -1)
        if [ -z "$pubdate" ]; then
            pubdate=$(echo "$entry" | grep -oP '(?<=<updated>)[^<]+' | head -1)
        fi
        
        # Skip if essential data missing
        [ -z "$title" ] && continue
        [ -z "$link" ] && continue
        
        # Default pubdate if missing
        [ -z "$pubdate" ] && pubdate=$(date -Iseconds)
        
        # Escape for JSON
        title_escaped=$(echo "$title" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\t/\\t/g' | tr '\n' ' ')
        
        # Add comma if not first
        if [ "$first" = true ]; then
            first=false
        else
            echo "," >> "$TEMP_FILE"
        fi
        
        cat >> "$TEMP_FILE" << EOF
  {
    "user": "$user",
    "title": "$title_escaped",
    "link": "$link",
    "pubDate": "$pubdate"
  }
EOF
    done
    
    sleep 1  # Be nice to the API
done

# Close JSON
echo '], "lastUpdated": "'$(date -Iseconds)'"}' >> "$TEMP_FILE"

# Move to final location
mv "$TEMP_FILE" "$OUTPUT_FILE"

echo "✓ X feed updated: $(date)"
echo "  Output: $OUTPUT_FILE"
