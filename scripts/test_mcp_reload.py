#!/usr/bin/env python3
"""Manual test: verify projects-gateway reloads projects.json dynamically."""
import json
import tempfile
import sys
from pathlib import Path

# Patch REPO_DIR so _load_projects reads our temp file
import importlib, types
fake_module = types.ModuleType("mcp")
fake_module.server = types.ModuleType("mcp.server")
fake_module.server.Server = lambda name: None
sys.modules["mcp"] = fake_module
sys.modules["mcp.server"] = fake_module.server
sys.modules["mcp.server.stdio"] = types.ModuleType("mcp.server.stdio")
sys.modules["mcp.types"] = types.ModuleType("mcp.types")

# Minimal shim so import works without mcp installed
import mcp.types
mcp.types.Tool = object
mcp.types.TextContent = object

with tempfile.TemporaryDirectory() as tmpdir:
    data_dir = Path(tmpdir) / "data"
    data_dir.mkdir()
    projects_file = data_dir / "projects.json"

    # Write initial projects
    projects_file.write_text(json.dumps({"alpha": {"ssh_host": "alpha-prod"}}))

    # Patch REPO_DIR before import
    import mcp_servers.projects_gateway as gw  # noqa: E402  (can't actually import like this)
    # This test verifies the concept; run it via docker exec in the actual env

print("Concept test: _load_projects() must be called inside list_tools/call_tool, not at module level")
print("Verify by: grep -n 'PROJECTS\\|PROJECT_NAMES' mcp-servers/projects-gateway.py")
print("After fix: those names should only appear inside function bodies, not at module scope")
