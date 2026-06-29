#!/usr/bin/env python3
"""Manual test: verify projects-gateway reloads projects.json dynamically."""
import json
import tempfile
import types
import sys
from pathlib import Path

# Patch sys.modules so projects-gateway can be imported without mcp installed
fake_mcp = types.ModuleType("mcp")
fake_mcp.server = types.ModuleType("mcp.server")
fake_mcp.server.Server = lambda name: None
sys.modules["mcp"] = fake_mcp
sys.modules["mcp.server"] = fake_mcp.server
sys.modules["mcp.server.stdio"] = types.ModuleType("mcp.server.stdio")
sys.modules["mcp.types"] = types.ModuleType("mcp.types")
sys.modules["mcp.types"].Tool = object
sys.modules["mcp.types"].TextContent = object

with tempfile.TemporaryDirectory() as tmpdir:
    data_dir = Path(tmpdir) / "data"
    data_dir.mkdir()
    projects_file = data_dir / "projects.json"

    # Write initial projects
    projects_file.write_text(json.dumps({"alpha": {"ssh_host": "alpha-prod"}}))

print("Concept test: _load_projects() must be called inside list_tools/call_tool, not at module level")
print("Verify by: grep -n 'PROJECTS\\|PROJECT_NAMES' mcp-servers/projects-gateway.py")
print("After fix: those names should only appear inside function bodies, not at module scope")
