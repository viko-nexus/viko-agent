# Skill: Media Generation via 9Router

Viko can generate images, text-to-speech audio, and transcribe speech using 9Router.
All calls use `$NINEROUTER_URL` (available in environment as `http://viko-9router:20128`).
Use the terminal tool to run curl commands from inside the container.

## Check Available Models First

```bash
curl $NINEROUTER_URL/v1/models/image | jq '.data[].id'   # image generation
curl $NINEROUTER_URL/v1/models/tts   | jq '.data[].id'   # text-to-speech
curl $NINEROUTER_URL/v1/models/stt   | jq '.data[].id'   # speech-to-text
```

If empty → that provider is not yet configured in 9Router. Ask Eksa to add the API key
in 9Router → Providers.

---

## Image Generation

`POST $NINEROUTER_URL/v1/images/generations`

```bash
# Save image file directly
curl -X POST "$NINEROUTER_URL/v1/images/generations?response_format=binary" \
  -H "Authorization: Bearer $NINEROUTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"gemini/gemini-3-pro-image-preview","prompt":"...","size":"1024x1024"}' \
  --output /tmp/output.png
```

Common models (check availability first): `openai/dall-e-3`, `gemini/gemini-3-pro-image-preview`,
`black-forest-labs/flux-pro`, `stability-ai/stable-diffusion-3`.

---

## Text-to-Speech

`POST $NINEROUTER_URL/v1/audio/speech`

```bash
# List voices for a provider
curl "$NINEROUTER_URL/v1/audio/voices?provider=edge-tts&lang=id" | jq '.data[].model'

# Generate audio
curl -X POST "$NINEROUTER_URL/v1/audio/speech" \
  -H "Authorization: Bearer $NINEROUTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"edge-tts/id-ID-ArdiNeural","input":"Hello, this is Viko"}' \
  --output /tmp/output.mp3
```

Common voice IDs: `edge-tts/id-ID-ArdiNeural` (male ID), `edge-tts/id-ID-GadisNeural` (female ID),
`el/<elevenlabs_voice_id>`, `openai/alloy`.

---

## Speech-to-Text (Transcription)

`POST $NINEROUTER_URL/v1/audio/transcriptions` (multipart/form-data)

```bash
curl -X POST "$NINEROUTER_URL/v1/audio/transcriptions" \
  -H "Authorization: Bearer $NINEROUTER_KEY" \
  -F "model=groq/whisper-large-v3" \
  -F "file=@/path/to/audio.mp3" \
  -F "language=id" \
  -F "response_format=text"
```

Common models: `groq/whisper-large-v3` (fast), `openai/whisper-1`, `deepgram/nova-3`,
`gemini/gemini-2.5-flash`.

---

---

## Browser Screenshot → Send to WhatsApp

Viko can take a screenshot from the browser and send it directly to WhatsApp.

### Take a screenshot with agent-browser

```bash
# Open URL and take screenshot
AGENT_BROWSER=/opt/hermes/node_modules/.bin/agent-browser

$AGENT_BROWSER open <url>
$AGENT_BROWSER screenshot /tmp/screenshot.png

# Full-page screenshot
$AGENT_BROWSER screenshot --full /tmp/screenshot.png

# Screenshot + close
$AGENT_BROWSER open <url> && $AGENT_BROWSER screenshot /tmp/ss.png && $AGENT_BROWSER close
```

### Send file to WhatsApp via bridge

The WhatsApp bridge runs at `http://localhost:3000` inside the container.
`chatId` is available from the current conversation context (format: `628xxx@s.whatsapp.net` for DM,
`120363xxx@g.us` for group).

```bash
# Send image
curl -s -X POST http://localhost:3000/send-media \
  -H "Content-Type: application/json" \
  -d '{
    "chatId": "<chatId>",
    "filePath": "/tmp/screenshot.png",
    "mediaType": "image",
    "caption": "Screenshot from <url>"
  }'

# Send document/PDF
curl -s -X POST http://localhost:3000/send-media \
  -H "Content-Type: application/json" \
  -d '{
    "chatId": "<chatId>",
    "filePath": "/tmp/report.pdf",
    "mediaType": "document",
    "fileName": "report.pdf"
  }'

# Send audio (TTS output)
curl -s -X POST http://localhost:3000/send-media \
  -H "Content-Type: application/json" \
  -d '{
    "chatId": "<chatId>",
    "filePath": "/tmp/output.mp3",
    "mediaType": "audio"
  }'
```

### Supported formats

| mediaType  | Extensions           |
|------------|----------------------|
| `image`    | jpg, jpeg, png, webp, gif |
| `video`    | mp4, webm, mkv       |
| `audio`    | mp3, ogg, wav, m4a   |
| `document` | pdf, docx, xlsx, etc |

### Full flow (screenshot → WhatsApp)

```bash
# 1. Take screenshot
AGENT_BROWSER=/opt/hermes/node_modules/.bin/agent-browser
$AGENT_BROWSER open https://example.com
$AGENT_BROWSER screenshot /tmp/ss.png
$AGENT_BROWSER close

# 2. Send to the active chat
curl -s -X POST http://localhost:3000/send-media \
  -H "Content-Type: application/json" \
  -d '{"chatId":"<chatId>","filePath":"/tmp/ss.png","mediaType":"image","caption":"Screenshot example.com"}'
```

---

---

## Browser Video Capture

Viko can record browser sessions as video and send them to WhatsApp.

**How it works:** Recording starts automatically when `browser_navigate` is called.
Session saved as `.webm` in `/opt/data/browser_recordings/`. Convert to `.mp4` before sending.

### Full flow

```bash
# Step 1: Do your browser work (recording starts automatically)
# Use browser_navigate, browser_click, browser_type, browser_scroll, etc.

# Step 2: Find the latest recording after the session ends
LATEST=$(ls -t /opt/data/browser_recordings/session_*.webm 2>/dev/null | head -1)

if [ -z "$LATEST" ]; then
  echo "No recording found"
  exit 1
fi

echo "Recording: $LATEST"

# Step 3: Convert webm → mp4 (WhatsApp needs mp4)
OUTPUT="/tmp/capture_$(date +%Y%m%d_%H%M%S).mp4"
ffmpeg -y -i "$LATEST" -c:v libx264 -preset fast -crf 28 -c:a aac "$OUTPUT"

echo "Converted: $OUTPUT"

# Step 4: Send to WhatsApp
curl -s -X POST http://localhost:3000/send-media \
  -H "Content-Type: application/json" \
  -d "{
    \"chatId\": \"<chatId>\",
    \"filePath\": \"$OUTPUT\",
    \"mediaType\": \"video\",
    \"caption\": \"Recording: <description>\"
  }"
```

### Tips

- **Long recordings**: WhatsApp limit ~64MB. If too big, trim with ffmpeg:
  ```bash
  ffmpeg -y -i "$LATEST" -t 60 -c:v libx264 -crf 28 -c:a aac /tmp/trimmed.mp4
  ```
- **Recordings auto-deleted after 72 hours** — send to WA promptly
- **Recording path**: `/opt/data/browser_recordings/session_YYYYMMDD_HHMMSS_<taskid>.webm`

---

---

## Chart Generation (matplotlib)

Generate charts from data and send to WhatsApp as image.

### Full flow

```python
# /tmp/chart.py
import matplotlib
matplotlib.use('Agg')  # headless, no display needed
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

fig, ax = plt.subplots(figsize=(10, 5))

# Example: line chart
labels = ['00:00', '06:00', '12:00', '18:00', '23:00']
values = [20, 45, 78, 55, 30]

ax.plot(labels, values, marker='o', linewidth=2, color='#2196F3')
ax.fill_between(range(len(labels)), values, alpha=0.15, color='#2196F3')
ax.set_title('CPU Usage — Today', fontsize=14, fontweight='bold')
ax.set_ylabel('Usage (%)')
ax.set_ylim(0, 100)
ax.grid(axis='y', alpha=0.3)
ax.set_xticks(range(len(labels)))
ax.set_xticklabels(labels)

plt.tight_layout()
plt.savefig('/tmp/chart.png', dpi=150, bbox_inches='tight')
plt.close()
print('Chart saved')
```

```bash
# Run and send
python3 /tmp/chart.py
curl -s -X POST http://localhost:3000/send-media \
  -H "Content-Type: application/json" \
  -d '{"chatId":"<chatId>","filePath":"/tmp/chart.png","mediaType":"image","caption":"CPU Usage Today"}'
```

### Chart types

| Type | ax method |
|------|-----------|
| Line | `ax.plot(x, y)` |
| Bar | `ax.bar(x, y)` |
| Horizontal bar | `ax.barh(x, y)` |
| Pie | `ax.pie(values, labels=labels)` |
| Area | `ax.fill_between(x, y)` |

### Tips
- Dark theme: `plt.style.use('dark_background')`
- Multiple series: call `ax.plot(...)` / `ax.bar(...)` multiple times + `ax.legend()`
- Format Y-axis Rupiah: `ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'Rp{x:,.0f}'))`

---

## Rules

- Always check `$NINEROUTER_URL/v1/models/<type>` before calling — models vary by config
- Files generated in `/tmp/` inside the container are ephemeral
- If a provider returns error 402/credits: ask Eksa to top up that provider's API key in 9Router
- For sending media: always get `chatId` from the active conversation context — never guess
- **Resending a file**: when asked to resend/kirim ulang, always include the full file path using
  `MEDIA:/path/to/file.pdf` in the reply, OR use curl to call the bridge directly. Never just say
  "Kirim ulang:" without a path — the delivery hook cannot find the file without it.
