#!/usr/bin/env python3
"""
Viko Tools — MCP Server

Reliable operations for Viko that require deterministic execution.
More reliable than SOUL.md instructions because tools appear explicitly
in the model's tool list and the model is trained to use available tools.

Tools:
  - send_browser_video   : convert latest webm recording → mp4 → send to WA
  - generate_chart       : matplotlib chart from data → send to WA as image
  - send_wa_file         : send any local file to WA
"""
import asyncio
import json
import subprocess
import sys
import os
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("viko-tools")

BRIDGE_URL = "http://localhost:3000"
RECORDINGS_DIR = Path("/opt/data/browser_recordings")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _send_to_wa(chat_id: str, file_path: str, media_type: str, caption: str = "") -> dict:
    payload = {"chatId": chat_id, "filePath": file_path, "mediaType": media_type}
    if caption:
        payload["caption"] = caption
    result = subprocess.run(
        ["curl", "-s", "-X", "POST", f"{BRIDGE_URL}/send-media",
         "-H", "Content-Type: application/json",
         "-d", json.dumps(payload)],
        capture_output=True, text=True, timeout=30,
    )
    try:
        return json.loads(result.stdout)
    except Exception:
        return {"raw": result.stdout, "stderr": result.stderr}


def _file_size_mb(path: str) -> float:
    try:
        return os.path.getsize(path) / (1024 * 1024)
    except Exception:
        return 0.0


# ── Tool definitions ───────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="send_browser_video",
            description=(
                "Convert the latest browser session recording to MP4 and send to WhatsApp. "
                "Use this INSTEAD OF taking screenshots and making GIFs whenever Eksa asks "
                "to record or capture a browser session as video. "
                "The recording starts automatically when any browser tool is used — "
                "just call this tool after the browser work is done."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": "string",
                        "description": "WhatsApp chat ID from the current conversation (e.g. 628xxx@s.whatsapp.net)",
                    },
                    "caption": {
                        "type": "string",
                        "description": "Caption text for the video message",
                    },
                },
                "required": ["chat_id", "caption"],
            },
        ),
        Tool(
            name="generate_chart",
            description=(
                "Generate a chart image from data using matplotlib and send it to WhatsApp. "
                "Use this when Eksa asks to create a chart, graph, or visualization from data. "
                "Supported types: line, bar, horizontal_bar, pie, area."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": "string",
                        "description": "WhatsApp chat ID from the current conversation",
                    },
                    "chart_type": {
                        "type": "string",
                        "enum": ["line", "bar", "horizontal_bar", "pie", "area"],
                        "description": "Type of chart to generate",
                    },
                    "labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Category labels (X axis for line/bar, slice names for pie)",
                    },
                    "values": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Numeric data values corresponding to each label",
                    },
                    "title": {
                        "type": "string",
                        "description": "Chart title",
                    },
                    "caption": {
                        "type": "string",
                        "description": "WhatsApp caption for the image message",
                    },
                    "y_label": {
                        "type": "string",
                        "description": "Y-axis label (optional, e.g. 'Usage (%)', 'Rp')",
                        "default": "",
                    },
                    "color": {
                        "type": "string",
                        "description": "Hex color for the chart (optional, default #2196F3)",
                        "default": "#2196F3",
                    },
                },
                "required": ["chat_id", "chart_type", "labels", "values", "title", "caption"],
            },
        ),
        Tool(
            name="send_wa_file",
            description=(
                "Send a local file to WhatsApp. Use for images, audio, PDFs, or any file "
                "that Viko has already generated or downloaded. "
                "media_type must be: image, video, audio, or document."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": "string",
                        "description": "WhatsApp chat ID from the current conversation",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Absolute path to the file inside the container (use /tmp/ for generated files)",
                    },
                    "media_type": {
                        "type": "string",
                        "enum": ["image", "video", "audio", "document"],
                        "description": "Media type: image (jpg/png/gif), video (mp4), audio (mp3/ogg), document (pdf/docx)",
                    },
                    "caption": {
                        "type": "string",
                        "description": "Optional caption text",
                        "default": "",
                    },
                },
                "required": ["chat_id", "file_path", "media_type"],
            },
        ),
    ]


# ── Tool implementations ───────────────────────────────────────────────────────

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "send_browser_video":
        return await _send_browser_video(arguments)
    elif name == "generate_chart":
        return await _generate_chart(arguments)
    elif name == "send_wa_file":
        return await _send_wa_file(arguments)
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _send_browser_video(args: dict) -> list[TextContent]:
    chat_id = args["chat_id"]
    caption = args.get("caption", "Recording")

    # Find latest webm
    webm_files = sorted(RECORDINGS_DIR.glob("session_*.webm"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not webm_files:
        return [TextContent(type="text", text="ERROR: No browser recording found in /opt/data/browser_recordings/. Make sure browser_navigate was used during the session.")]

    latest_webm = str(webm_files[0])

    # Convert to mp4
    output = f"/tmp/viko_video_{os.getpid()}.mp4"
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", latest_webm,
         "-c:v", "libx264", "-preset", "fast", "-crf", "28",
         "-c:a", "aac", output],
        capture_output=True, text=True, timeout=120,
    )
    if not Path(output).exists():
        return [TextContent(type="text", text=f"ERROR: ffmpeg conversion failed.\n{result.stderr[-500:]}")]

    size_mb = _file_size_mb(output)

    # Send to WA
    send_result = _send_to_wa(chat_id, output, "video", caption)

    return [TextContent(type="text", text=(
        f"Video sent: {Path(latest_webm).name} → {Path(output).name} ({size_mb:.1f} MB)\n"
        f"Bridge: {json.dumps(send_result)}"
    ))]


async def _generate_chart(args: dict) -> list[TextContent]:
    chat_id = args["chat_id"]
    chart_type = args["chart_type"]
    labels = args["labels"]
    values = args["values"]
    title = args["title"]
    caption = args.get("caption", title)
    y_label = args.get("y_label", "")
    color = args.get("color", "#2196F3")

    if len(labels) != len(values):
        return [TextContent(type="text", text=f"ERROR: labels ({len(labels)}) and values ({len(values)}) must have the same length")]

    output = f"/tmp/viko_chart_{os.getpid()}.png"

    chart_script = f"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

fig, ax = plt.subplots(figsize=(10, 5))
labels = {json.dumps(labels)}
values = {json.dumps(values)}
color = {json.dumps(color)}

if {json.dumps(chart_type)} == 'line':
    ax.plot(range(len(labels)), values, marker='o', linewidth=2, color=color)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30 if len(labels) > 6 else 0, ha='right')
elif {json.dumps(chart_type)} == 'bar':
    ax.bar(range(len(labels)), values, color=color, alpha=0.85)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30 if len(labels) > 6 else 0, ha='right')
elif {json.dumps(chart_type)} == 'horizontal_bar':
    ax.barh(range(len(labels)), values, color=color, alpha=0.85)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
elif {json.dumps(chart_type)} == 'area':
    ax.fill_between(range(len(labels)), values, alpha=0.4, color=color)
    ax.plot(range(len(labels)), values, linewidth=2, color=color)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30 if len(labels) > 6 else 0, ha='right')
elif {json.dumps(chart_type)} == 'pie':
    ax.pie(values, labels=labels, autopct='%1.1f%%', colors=[color])
    ax.axis('equal')

ax.set_title({json.dumps(title)}, fontsize=14, fontweight='bold', pad=12)
if {json.dumps(y_label)} and {json.dumps(chart_type)} != 'pie':
    ax.set_ylabel({json.dumps(y_label)})
if {json.dumps(chart_type)} not in ('pie', 'horizontal_bar'):
    ax.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig({json.dumps(output)}, dpi=150, bbox_inches='tight')
plt.close()
print('OK')
"""

    result = subprocess.run(
        [sys.executable, "-c", chart_script],
        capture_output=True, text=True, timeout=30,
    )
    if not Path(output).exists():
        return [TextContent(type="text", text=f"ERROR: Chart generation failed.\n{result.stdout}\n{result.stderr}")]

    size_kb = int(_file_size_mb(output) * 1024)
    send_result = _send_to_wa(chat_id, output, "image", caption)

    return [TextContent(type="text", text=(
        f"Chart sent: {chart_type} '{title}' ({size_kb} KB)\n"
        f"Bridge: {json.dumps(send_result)}"
    ))]


async def _send_wa_file(args: dict) -> list[TextContent]:
    chat_id = args["chat_id"]
    file_path = args["file_path"]
    media_type = args["media_type"]
    caption = args.get("caption", "")

    if not Path(file_path).exists():
        return [TextContent(type="text", text=f"ERROR: File not found: {file_path}")]

    size_mb = _file_size_mb(file_path)
    send_result = _send_to_wa(chat_id, file_path, media_type, caption)

    return [TextContent(type="text", text=(
        f"Sent: {file_path} ({size_mb:.1f} MB) as {media_type}\n"
        f"Bridge: {json.dumps(send_result)}"
    ))]


# ── Entry point ────────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
