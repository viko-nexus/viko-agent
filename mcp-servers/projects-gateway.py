#!/usr/bin/env python3
"""
Viko Projects Gateway — MCP Server

Provides SSH execution tools for all active projects.
Runs as a stdio MCP server, registered in config.yaml.

Project list is loaded from data/projects.json (gitignored, deployment-specific).
See mcp-servers/projects.json.example for the expected format.
"""
import asyncio
import json
import subprocess
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("viko-projects-gateway")

REPO_DIR = Path(__file__).parent.parent

def _load_projects() -> dict:
    """Load project → ssh_host mapping from data/projects.json.

    The file is gitignored and deployment-specific. Each deployer populates it
    during initial setup. Returns an empty dict if the file does not exist.
    """
    config_path = REPO_DIR / "data" / "projects.json"
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}

PROJECTS: dict[str, dict] = _load_projects()
PROJECT_NAMES: list[str] = list(PROJECTS.keys())


@server.list_tools()
async def list_tools() -> list[Tool]:
    projects_str = ", ".join(PROJECT_NAMES) if PROJECT_NAMES else "(none configured)"
    return [
        Tool(
            name="ssh_exec",
            description=(
                "Run a shell command on a project's production server via SSH. "
                "Use this for any task requiring server access: checking logs, "
                "querying databases, inspecting running containers, etc."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "enum": PROJECT_NAMES,
                        "description": f"Project slug. Available: {projects_str}",
                    },
                    "command": {
                        "type": "string",
                        "description": "Shell command to run on the production server",
                    },
                },
                "required": ["project", "command"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name != "ssh_exec":
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    project = arguments.get("project", "")
    command = arguments.get("command", "")

    if project not in PROJECTS:
        return [TextContent(type="text", text=f"Unknown project: {project}. Available: {PROJECT_NAMES}")]

    ssh_host = PROJECTS[project]["ssh_host"]

    try:
        result = subprocess.run(
            ["ssh", "-F", "/opt/data/.ssh/config", "-o", "ConnectTimeout=15", ssh_host, command],
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        if not output.strip():
            output = "(no output)"
        return [TextContent(type="text", text=output)]

    except subprocess.TimeoutExpired:
        return [TextContent(type="text", text="Command timed out after 60 seconds")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
