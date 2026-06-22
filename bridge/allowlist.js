/**
 * allowlist.js — WhatsApp phone number matching utilities
 *
 * Phone numbers in env vars are stored without '+' (e.g. "6281234567890").
 * Sender IDs from Baileys arrive as "6281234567890@s.whatsapp.net" or
 * "6281234567890:12@s.whatsapp.net" (multi-device LID format).
 */

/**
 * Parse a comma-separated list of phone numbers.
 * Returns ['*'] for wildcard, [] for empty string.
 */
export function parseAllowedUsers(str) {
  if (!str || !str.trim()) return [];
  const trimmed = str.trim();
  if (trimmed === '*') return ['*'];
  return trimmed
    .split(',')
    .map((s) => s.trim().replace(/^\+/, ''))
    .filter(Boolean);
}

/**
 * Normalize a WhatsApp sender ID to a bare phone number.
 * "6281234567890@s.whatsapp.net" → "6281234567890"
 * "6281234567890:12@s.whatsapp.net" → "6281234567890"
 */
export function normalizePhone(senderId) {
  return String(senderId || '')
    .split('@')[0]
    .split(':')[0];
}

/**
 * Check whether a sender ID is in the allow list.
 */
export function matchesAllowedUser(senderId, allowList) {
  if (!allowList || allowList.length === 0) return false;
  if (allowList.includes('*')) return true;
  const phone = normalizePhone(senderId);
  return allowList.some((a) => phone === a);
}
