#!/usr/bin/env python3
"""
Viko Projects Gateway — MCP Server
Provides SSH execution and database query tools for all active projects.
Runs as a stdio MCP server, registered in config.yaml.
"""
import asyncio
import subprocess
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("viko-projects-gateway")

PROJECTS = {
    "mankop":      {"ssh_host": "mankop-prod"},
    "forecastinn": {"ssh_host": "forecastinn-prod"},
    "luxso":       {"ssh_host": "luxso-prod"},
    "forecastcrm": {"ssh_host": "forecastcrm-prod"},
}

PROJECT_NAMES = list(PROJECTS.keys())


@server.list_tools()
async def list_tools() -> list[Tool]:
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
                        "description": "Project name: mankop, forecastinn, luxso, or forecastcrm",
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
        return [TextContent(type="text", text=f"Unknown project: {project}. Use one of: {PROJECT_NAMES}")]

    ssh_host = PROJECTS[project]["ssh_host"]

    try:
        result = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=15", ssh_host, command],
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
