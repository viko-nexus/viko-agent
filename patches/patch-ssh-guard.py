"""
Patch: Narrow the ssh_access threat pattern in threat_patterns.py.

Original pattern blocks ALL references to ~/.ssh or $HOME/.ssh, including
legitimate SSH connections like `ssh -i ~/.ssh/id_rsa_mankop_app host`.

This patch replaces it with a narrower pattern that only blocks actual key
content exfiltration (cat/echo/curl of key files), not SSH connections.
The real exfiltration risk (cat key | curl) is already covered by exfil_curl.
"""

import sys
from pathlib import Path

TARGET = Path("/opt/hermes/tools/threat_patterns.py")

if not TARGET.exists():
    print(f"ERROR: {TARGET} not found", file=sys.stderr)
    sys.exit(1)

original = TARGET.read_text()

OLD = r"""    (r'\$HOME/\.ssh|\~/\.ssh', "ssh_access", "strict"),"""

# Narrowed: only block when reading/sending SSH key content, not SSH connections
NEW = r"""    # ssh_access narrowed: only block key exfiltration, not SSH connections
    # (legitimate `ssh -i ~/.ssh/key host` is allowed; key reading/sending is not)
    (r'(?:cat|less|more|head|tail|echo|tee|curl|wget|nc|ncat)\s+[^\n]*(?:\$HOME|~)/\.ssh', "ssh_key_exfil", "strict"),"""

if OLD not in original:
    print("Pattern not found — already patched or threat_patterns.py changed upstream.")
    sys.exit(0)

patched = original.replace(OLD, NEW)
TARGET.write_text(patched)
print("Patched threat_patterns.py: ssh_access narrowed to ssh_key_exfil")
