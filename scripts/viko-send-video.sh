#!/bin/bash
# Usage: viko-send-video <chatId> "<caption>"
CHAT_ID="${1:?Usage: viko-send-video <chatId> <caption>}"
CAPTION="${2:-Recording}"

LATEST=$(ls -t /opt/data/browser_recordings/session_*.webm 2>/dev/null | head -1)
if [ -z "$LATEST" ]; then
  echo "ERROR: No browser recording found in /opt/data/browser_recordings/"
  exit 1
fi

OUTPUT="/tmp/viko_video_$(date +%Y%m%d_%H%M%S).mp4"
echo "Converting: $LATEST -> $OUTPUT"
ffmpeg -y -i "$LATEST" -c:v libx264 -preset fast -crf 28 -c:a aac "$OUTPUT" 2>&1 | tail -2

if [ ! -f "$OUTPUT" ]; then
  echo "ERROR: ffmpeg conversion failed"
  exit 1
fi

SIZE=$(du -h "$OUTPUT" | cut -f1)
echo "Sending: $OUTPUT ($SIZE)"

RESULT=$(curl -s -X POST http://localhost:3000/send-media \
  -H "Content-Type: application/json" \
  -d "{\"chatId\":\"$CHAT_ID\",\"filePath\":\"$OUTPUT\",\"mediaType\":\"video\",\"caption\":\"$CAPTION\"}")

echo "Bridge: $RESULT"
echo "Done: $OUTPUT ($SIZE)"
