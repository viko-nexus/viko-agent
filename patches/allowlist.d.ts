// Type declarations for './allowlist.js', which patches/whatsapp-bridge.js imports
// at runtime from Hermes' own bridge dir (it is NOT shipped in patches/ — the
// Dockerfile only overlays whatsapp-bridge.js). This sidecar lets checkJs resolve
// the import without a runtime file. It mirrors HERMES' allowlist.js (the file that
// actually runs), where parseAllowedUsers returns a Set with LID-aware matching.
export function parseAllowedUsers(raw: string): Set<string>;
export function matchesAllowedUser(
  senderId: string,
  allowed: Set<string>,
  sessionDir?: string,
): boolean;
