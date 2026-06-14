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

## Rules

- Always check `$NINEROUTER_URL/v1/models/<type>` before calling — models vary by config
- Files generated in `/tmp/` inside the container are ephemeral
- If a provider returns error 402/credits: ask Eksa to top up that provider's API key in 9Router
- For sending media: always get `chatId` from the active conversation context — never guess
