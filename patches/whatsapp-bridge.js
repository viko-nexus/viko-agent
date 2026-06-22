#!/usr/bin/env node
/**
 * Hermes Agent WhatsApp Bridge
 *
 * Standalone Node.js process that connects to WhatsApp via Baileys
 * and exposes HTTP endpoints for the Python gateway adapter.
 *
 * Endpoints (matches gateway/platforms/whatsapp.py expectations):
 *   GET  /messages       - Long-poll for new incoming messages
 *   POST /send           - Send a message { chatId, message, replyTo? }
 *   POST /edit           - Edit a sent message { chatId, messageId, message }
 *   POST /send-media     - Send media natively { chatId, filePath, mediaType?, caption?, fileName? }
 *   POST /typing         - Send typing indicator { chatId }
 *   GET  /chat/:id       - Get chat info
 *   GET  /health         - Health check
 *
 * Usage:
 *   node bridge.js --port 3000 --session ~/.hermes/whatsapp/session
 */

import {
  makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  downloadMediaMessage,
} from '@whiskeysockets/baileys';
import express from 'express';
import { Boom } from '@hapi/boom';
import pino from 'pino';
import path from 'path';
import {
  mkdirSync,
  readFileSync,
  writeFileSync,
  existsSync,
  readdirSync,
  unlinkSync,
  watch,
  statSync,
  appendFileSync,
  writeSync,
} from 'fs';
import { randomBytes } from 'crypto';
import { execSync } from 'child_process';
import { tmpdir } from 'os';
import qrcode from 'qrcode-terminal';
import { matchesAllowedUser, parseAllowedUsers } from './allowlist.js';

// Parse CLI args
const args = process.argv.slice(2);
function getArg(name, defaultVal) {
  const idx = args.indexOf(`--${name}`);
  return idx !== -1 && args[idx + 1] ? args[idx + 1] : defaultVal;
}

const WHATSAPP_DEBUG =
  typeof process !== 'undefined' &&
  process.env &&
  typeof process.env.WHATSAPP_DEBUG === 'string' &&
  ['1', 'true', 'yes', 'on'].includes(process.env.WHATSAPP_DEBUG.toLowerCase());

const PORT = parseInt(getArg('port', '3000'), 10);
const SESSION_DIR = getArg(
  'session',
  path.join(process.env.HOME || '~', '.hermes', 'whatsapp', 'session'),
);
const IMAGE_CACHE_DIR = path.join(process.env.HOME || '~', '.hermes', 'image_cache');
// Media is downloaded by the ADMIN bridge into these cache dirs and referenced by
// ABSOLUTE PATH. The admin's own Hermes reads the files directly. Project (relay)
// containers can't read the admin's filesystem, and Hermes' SSRF guard (is_safe_url)
// blocks loopback HTTP fetches — so the relay /messages handler pre-downloads each
// referenced file to the SAME absolute path locally (see _prefetchRelayMedia),
// making the path valid inside the project container too.
const DOCUMENT_CACHE_DIR = path.join(process.env.HOME || '~', '.hermes', 'document_cache');
const AUDIO_CACHE_DIR = path.join(process.env.HOME || '~', '.hermes', 'audio_cache');
// Owning chat JID per cached media basename. Populated where inbound media is written
// to a cache dir, consumed by GET /media/:file to enforce per-owner access (A1) so a
// project relay can only pull files that belong to its own group.
const _mediaOwnerByFile = new Map();
const MAX_MEDIA_OWNER_ENTRIES = 2000;
function _tagMediaOwner(filePath, ownerJid) {
  if (!filePath || !ownerJid) return;
  _mediaOwnerByFile.set(path.basename(filePath), ownerJid);
  if (_mediaOwnerByFile.size > MAX_MEDIA_OWNER_ENTRIES) {
    _mediaOwnerByFile.delete(_mediaOwnerByFile.keys().next().value);
  }
}
// Last media seen per chat, so a request sent right after a file (as a separate
// message — e.g. forward a .docx, then "buatin pdf viko") can still reach the file.
const _recentMediaByChat = {};
const RECENT_MEDIA_WINDOW_MS = 5 * 60 * 1000;

// Most recent inbound message per chat, kept so the bot's reply can quote it
// (WhatsApp reply-threading). Bounded implicitly by the number of active chats.
const _lastInboundByChat = {};
const QUOTE_WINDOW_MS = 15 * 60 * 1000;
// Outbound de-dup: the gateway's MEDIA: delivery and the viko-media-autosend hook can
// both try to send the same file — drop a duplicate (same chat+name+size) within a window.
const _recentSends = {};
const SEND_DEDUP_MS = 90 * 1000;
const PAIR_ONLY = args.includes('--pair-only');
const WHATSAPP_MODE = getArg('mode', process.env.WHATSAPP_MODE || 'self-chat'); // "bot" or "self-chat"
const ALLOWED_USERS = parseAllowedUsers(process.env.WHATSAPP_ALLOWED_USERS || '');
// Groups listed here bypass the per-user allowlist — all members can trigger the bot.
// Populated by add-project.py when a project is onboarded.
const TRUSTED_GROUPS = new Set(
  (process.env.WHATSAPP_TRUSTED_GROUPS || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean),
);
// Owner phone(s) — derived from WHATSAPP_HOME_CHANNEL. Only owner can authorize execution.
const OWNER_PHONES = parseAllowedUsers(process.env.WHATSAPP_HOME_CHANNEL || '');
// Allow group messages in self-chat mode (filtered by Python gateway via REQUIRE_MENTION)
const SELF_CHAT_ALLOW_GROUPS = ['1', 'true', 'yes', 'on'].includes(
  (process.env.WHATSAPP_SELF_CHAT_ALLOW_GROUPS || '').toLowerCase(),
);
const DEFAULT_REPLY_PREFIX = '⚕ *Hermes Agent*\n────────────\n';
const REPLY_PREFIX =
  process.env.WHATSAPP_REPLY_PREFIX === undefined
    ? DEFAULT_REPLY_PREFIX
    : process.env.WHATSAPP_REPLY_PREFIX.replace(/\\n/g, '\n');
const MAX_MESSAGE_LENGTH = parseInt(process.env.WHATSAPP_MAX_MESSAGE_LENGTH || '4096', 10);
const CHUNK_DELAY_MS = parseInt(process.env.WHATSAPP_CHUNK_DELAY_MS || '300', 10);
// Per-call timeout for sock.sendMessage(). Baileys occasionally hangs forever
// when uploading media to WhatsApp servers (and, less often, on text sends),
// which pins the bridge's HTTP handler until the upstream aiohttp timeout
// fires. Fail fast instead so the gateway can surface a real error and retry.
const SEND_TIMEOUT_MS = parseInt(process.env.WHATSAPP_SEND_TIMEOUT_MS || '60000', 10);

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function sendWithTimeout(chatId, payload, timeoutMs = SEND_TIMEOUT_MS) {
  let timer;
  const timeoutPromise = new Promise((_, reject) => {
    timer = setTimeout(
      () => reject(new Error(`sendMessage timed out after ${timeoutMs / 1000}s`)),
      timeoutMs,
    );
  });
  // Reply-threaded: quote the chat's most recent inbound message so the bot's reply
  // renders as a WhatsApp reply to whoever it's answering — clearer in a busy group.
  // Best-effort: only when a recent inbound is on record; never blocks a send.
  const _opts = {};
  const _q = _lastInboundByChat[chatId];
  if (_q && _q.msg && Date.now() - _q.ts < QUOTE_WINDOW_MS) _opts.quoted = _q.msg;
  return Promise.race([sock.sendMessage(chatId, payload, _opts), timeoutPromise]).finally(() =>
    clearTimeout(timer),
  );
}

function formatOutgoingMessage(message) {
  // Strip internal scope/role markers the model may have echoed back. They're injected
  // into INBOUND messages for the gateway (scope binding, owner-gate) and must NEVER
  // reach the user — covers both the bracketed tag and any verbalized "CTX". Deterministic
  // backstop so a leak can't depend on the model honoring a soft rule.
  message = String(message ?? '')
    .replace(/\[(?:CTX|READ-ONLY MEMBER|Mentioned)\b[^\]]*\]/gi, '')
    .replace(/\bCTX\b[:.\s]*/gi, '')
    .replace(/^[\s:–—-]+/, '');
  if (/^[a-z]/.test(message)) message = message.charAt(0).toUpperCase() + message.slice(1);
  // In bot mode, messages come from a different number so the prefix is
  // redundant — the sender identity is already clear.  Only prepend in
  // self-chat mode where bot and user share the same number.
  if (WHATSAPP_MODE !== 'self-chat') return message;
  return REPLY_PREFIX ? `${REPLY_PREFIX.trimEnd()} ${message}` : message;
}

function splitLongMessage(message, maxLength = MAX_MESSAGE_LENGTH) {
  const text = String(message || '');
  if (!text) return [];
  if (!Number.isFinite(maxLength) || maxLength < 1 || text.length <= maxLength) {
    return [text];
  }

  const chunks = [];
  let remaining = text;
  while (remaining.length > maxLength) {
    let splitAt = remaining.lastIndexOf('\n', maxLength);
    if (splitAt < Math.floor(maxLength / 2)) {
      splitAt = remaining.lastIndexOf(' ', maxLength);
    }
    if (splitAt < 1) splitAt = maxLength;

    chunks.push(remaining.slice(0, splitAt).trimEnd());
    remaining = remaining.slice(splitAt).trimStart();
  }
  if (remaining) chunks.push(remaining);
  return chunks;
}

function trackSentMessageId(sent) {
  if (sent?.key?.id) {
    recentlySentIds.add(sent.key.id);
    if (recentlySentIds.size > MAX_RECENT_IDS) {
      recentlySentIds.delete(recentlySentIds.values().next().value);
    }
  }
}

function normalizeWhatsAppId(value) {
  if (!value) return '';
  return String(value).replace(':', '@');
}

function getMessageContent(msg) {
  const content = msg?.message || {};
  if (content.ephemeralMessage?.message) return content.ephemeralMessage.message;
  if (content.viewOnceMessage?.message) return content.viewOnceMessage.message;
  if (content.viewOnceMessageV2?.message) return content.viewOnceMessageV2.message;
  if (content.documentWithCaptionMessage?.message)
    return content.documentWithCaptionMessage.message;
  if (content.templateMessage?.hydratedTemplate) return content.templateMessage.hydratedTemplate;
  if (content.buttonsMessage) return content.buttonsMessage;
  if (content.listMessage) return content.listMessage;
  return content;
}

function getContextInfo(messageContent) {
  if (!messageContent || typeof messageContent !== 'object') return {};
  for (const value of Object.values(messageContent)) {
    if (value && typeof value === 'object' && value.contextInfo) {
      return value.contextInfo;
    }
  }
  return {};
}

mkdirSync(SESSION_DIR, { recursive: true });

// Build LID → phone map from session files. WhatsApp persists the mapping in two
// shapes; read BOTH so group participants (now returned as @lid) resolve to a real
// phone regardless of which direction was stored:
//   lid-mapping-{phone}.json         → body is the LID   (keyed by phone)
//   lid-mapping-{lid}_reverse.json   → body is the phone (keyed by lid)
function buildLidMap() {
  const map = {};
  try {
    for (const f of readdirSync(SESSION_DIR)) {
      const rev = f.match(/^lid-mapping-(\d+)_reverse\.json$/);
      if (rev) {
        const lid = rev[1];
        const phone = JSON.parse(readFileSync(path.join(SESSION_DIR, f), 'utf8'));
        if (phone) map[String(lid)] = String(phone);
        continue;
      }
      const fwd = f.match(/^lid-mapping-(\d+)\.json$/);
      if (fwd) {
        const phone = fwd[1];
        const lid = JSON.parse(readFileSync(path.join(SESSION_DIR, f), 'utf8'));
        if (lid) map[String(lid)] = String(phone);
      }
    }
  } catch {}
  return map;
}
let _lidToPhone = buildLidMap();

// Display names learned from inbound messages (pushName), keyed by the sender's
// number (lid or phone). Lets /group/:jid/participants label members who've spoken;
// members who never sent a message stay unnamed (WhatsApp exposes no name otherwise).
const _nameByNumber = {};

const logger = pino({ level: 'warn' });

// F3-tee: SECURITY/deny events also go to docker logs. The gateway redirects the
// bridge's stdout to a file, so security denials never surface in `docker logs`.
// Write these specific events directly to fd 2 (stderr) so they're visible there.
// Deny/security events ONLY — never normal-traffic spam.
function _securityLog(line) {
  try {
    writeSync(2, `[bridge][security] ${line}\n`);
  } catch {}
}

// Message queue for polling
const messageQueue = []; // kept for backward compat (admin Hermes, no port filter)
const messageQueues = {}; // per-port queues: { "8101": [...], "8102": [...] }
const globalQueue = []; // unrouted messages → Admin Hermes

// ── Routing table (routing.json hot-reload) ──────────────────────────────
const ROUTING_FILE =
  process.env.ROUTING_FILE ||
  path.join(process.env.HOME || '/opt/data', 'projects/viko-agent/data/bridge/routing.json');

// Prototype-free maps: attacker-controlled keys (a relay token / jid from a request
// header or param) must NOT resolve to inherited Object.prototype members. With a
// plain {} a token of "constructor"/"__proto__"/"toString" would make _tokenToJid[token]
// truthy and slip past the `if (!jid)` scope gate — so use Object.create(null).
let _routing = Object.create(null); // { "jid@g.us": 8101 }     — normalized, inbound routing
let _tokenToJid = Object.create(null); // { "<relay_token>": "jid@g.us" } — outbound scope checks
let _jidToSlug = Object.create(null); // { "jid@g.us": "slug" }  — group → project, for scope stamping

function _loadRouting() {
  let rawText;
  try {
    rawText = readFileSync(ROUTING_FILE, 'utf8');
  } catch {
    // File genuinely doesn't exist / unreadable as missing → no routes.
    _routing = Object.create(null);
    _tokenToJid = Object.create(null);
    _jidToSlug = Object.create(null);
    return;
  }
  // Empty file → no routes (legitimate "no projects yet" state).
  if (!rawText || !rawText.trim()) {
    _routing = Object.create(null);
    _tokenToJid = Object.create(null);
    _jidToSlug = Object.create(null);
    return;
  }
  try {
    const raw = JSON.parse(rawText);
    const routing = Object.create(null),
      tokenToJid = Object.create(null),
      jidToSlug = Object.create(null);
    for (const [jid, val] of Object.entries(raw)) {
      if (val && typeof val === 'object') {
        // New schema: { jid: { port, slug, relay_token } }
        if (val.port != null) routing[jid] = val.port;
        if (val.relay_token) tokenToJid[val.relay_token] = jid;
        if (val.slug) jidToSlug[jid] = val.slug;
      } else {
        // Legacy schema: { jid: port }
        routing[jid] = val;
      }
    }
    _routing = routing;
    _tokenToJid = tokenToJid;
    _jidToSlug = jidToSlug;
    console.log(
      `[bridge] routing.json loaded: ${Object.keys(_routing).length} routes, ${Object.keys(_tokenToJid).length} relay tokens`,
    );
  } catch (e) {
    // Fail-closed (D4): the file EXISTS and is NON-EMPTY but failed to parse —
    // likely a transient half-written write. Do NOT wipe live routes + relay
    // tokens; keep the previously-loaded maps so existing projects stay routable.
    console.warn(
      `[bridge] routing.json parse failed, keeping previous routes (${Object.keys(_routing).length} routes): ${e.message}`,
    );
  }
}

_loadRouting();
// Ensure directory exists before watching
let _reloadTimer;
try {
  const _routingDir = path.dirname(ROUTING_FILE);
  watch(_routingDir, { persistent: false }, (ev, fn) => {
    if (fn === path.basename(ROUTING_FILE)) {
      clearTimeout(_reloadTimer);
      _reloadTimer = setTimeout(_loadRouting, 50);
    }
  });
} catch {}

// ── Relay mode (project Hermes instances) ────────────────────────────────
const RELAY_MODE = ['1', 'true', 'yes'].includes(
  (process.env.WHATSAPP_RELAY_MODE || '').toLowerCase(),
);
const RELAY_TARGET = process.env.WHATSAPP_RELAY_TARGET || 'http://viko-hermes-admin:3000';
const PORT_FILTER = process.env.WHATSAPP_PORT_FILTER || '';
// Per-container relay credential. The admin bridge maps this token → the one JID
// this container is allowed to send to. Absent for the admin container itself.
const RELAY_TOKEN = process.env.HERMES_RELAY_TOKEN || '';
const _relayHeaders = () => ({
  'Content-Type': 'application/json',
  Host: 'viko-hermes-admin',
  ...(RELAY_TOKEN ? { Authorization: `Bearer ${RELAY_TOKEN}` } : {}),
});

const MAX_QUEUE_SIZE = 100;

// Track recently sent message IDs to prevent echo-back loops with media
const recentlySentIds = new Set();
const MAX_RECENT_IDS = 50;

let sock = null;
let connectionState = 'disconnected';

async function startSocket() {
  const { state, saveCreds } = await useMultiFileAuthState(SESSION_DIR);
  const { version } = await fetchLatestBaileysVersion();

  sock = makeWASocket({
    version,
    auth: state,
    logger,
    printQRInTerminal: false,
    browser: ['Hermes Agent', 'Chrome', '120.0'],
    syncFullHistory: false,
    markOnlineOnConnect: false,
    // Required for Baileys 7.x: without this, incoming messages that need
    // E2EE session re-establishment are silently dropped (msg.message === null)
    getMessage: async (_key) => {
      // We don't maintain a message store, so return a placeholder.
      // This is enough for Baileys to complete the retry handshake.
      return { conversation: '' };
    },
  });

  sock.ev.on('creds.update', () => {
    saveCreds();
    _lidToPhone = buildLidMap();
  });

  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      console.log('\n📱 Scan this QR code with WhatsApp on your phone:\n');
      qrcode.generate(qr, { small: true });
      console.log('\nWaiting for scan...\n');
    }

    if (connection === 'close') {
      const reason = new Boom(lastDisconnect?.error)?.output?.statusCode;
      connectionState = 'disconnected';

      if (reason === DisconnectReason.loggedOut) {
        console.log('❌ Logged out. Delete session and restart to re-authenticate.');
        process.exit(1);
      } else {
        // 515 = restart requested (common after pairing). Always reconnect.
        if (reason === 515) {
          console.log('↻ WhatsApp requested restart (code 515). Reconnecting...');
        } else {
          console.log(`⚠️  Connection closed (reason: ${reason}). Reconnecting in 3s...`);
        }
        setTimeout(startSocket, reason === 515 ? 1000 : 3000);
      }
    } else if (connection === 'open') {
      connectionState = 'connected';
      console.log('✅ WhatsApp connected!');
      if (PAIR_ONLY) {
        console.log('✅ Pairing complete. Credentials saved.');
        // Give Baileys a moment to flush creds, then exit cleanly
        setTimeout(() => process.exit(0), 2000);
      }
    }
  });

  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    // In self-chat mode, your own messages commonly arrive as 'append' rather
    // than 'notify'. Accept both and filter agent echo-backs below.
    if (type !== 'notify' && type !== 'append') return;

    const botIds = Array.from(
      new Set(
        [normalizeWhatsAppId(sock.user?.id), normalizeWhatsAppId(sock.user?.lid)].filter(Boolean),
      ),
    );

    for (const msg of messages) {
      if (!msg.message) continue;

      const chatId = msg.key.remoteJid;
      if (WHATSAPP_DEBUG) {
        try {
          console.log(
            JSON.stringify({
              event: 'upsert',
              type,
              fromMe: !!msg.key.fromMe,
              chatId,
              senderId: msg.key.participant || chatId,
              messageKeys: Object.keys(msg.message || {}),
            }),
          );
        } catch {}
      }
      const senderId = msg.key.participant || chatId;
      const isGroup = chatId.endsWith('@g.us');
      const senderNumber = senderId.replace(/@.*/, '');

      // Learn display names for the participants endpoint (members who've spoken).
      if (!msg.key.fromMe && msg.pushName && senderNumber) {
        _nameByNumber[senderNumber] = msg.pushName;
      }
      // Remember the latest inbound per chat so the bot's reply can quote it (reply-threading).
      if (!msg.key.fromMe && msg.message) {
        _lastInboundByChat[chatId] = { msg, ts: Date.now() };
      }

      // Handle fromMe messages based on mode
      if (msg.key.fromMe) {
        if (chatId.includes('status')) continue;
        // In self-chat mode, allow group messages if SELF_CHAT_ALLOW_GROUPS=true
        // Python gateway handles REQUIRE_MENTION + group_policy filtering
        if (isGroup && !SELF_CHAT_ALLOW_GROUPS) continue;

        if (WHATSAPP_MODE === 'bot') {
          // Bot mode: separate number. ALL fromMe are echo-backs of our own replies — skip.
          continue;
        }

        // Self-chat mode: only allow messages in the user's own self-chat
        // WhatsApp now uses LID (Linked Identity Device) format: 67427329167522@lid
        // AND classic format: 34652029134@s.whatsapp.net
        // sock.user has both: { id: "number:10@s.whatsapp.net", lid: "lid_number:10@lid" }
        const myNumber = (sock.user?.id || '').replace(/:.*@/, '@').replace(/@.*/, '');
        const myLid = (sock.user?.lid || '').replace(/:.*@/, '@').replace(/@.*/, '');
        const chatNumber = chatId.replace(/@.*/, '');
        const isSelfChat = (myNumber && chatNumber === myNumber) || (myLid && chatNumber === myLid);
        // Allow group fromMe messages if SELF_CHAT_ALLOW_GROUPS=true
        if (!isSelfChat && !(isGroup && SELF_CHAT_ALLOW_GROUPS)) continue;
      }

      // Handle !fromMe messages (from other people) based on mode.
      // Self-chat mode only responds to the user's own messages to
      // themselves — stranger DMs must never reach the Python gateway,
      // otherwise a pairing-code reply fires in response to arbitrary
      // incoming messages (#8389).
      // Exception: group messages are allowed when SELF_CHAT_ALLOW_GROUPS=true,
      // Python gateway handles REQUIRE_MENTION + group_policy filtering.
      if (!msg.key.fromMe) {
        if (WHATSAPP_MODE === 'self-chat') {
          if (!isGroup || !SELF_CHAT_ALLOW_GROUPS) {
            try {
              console.log(
                JSON.stringify({
                  event: 'ignored',
                  reason: 'self_chat_mode_rejects_non_self',
                  chatId,
                  senderId,
                }),
              );
            } catch {}
            continue;
          }
          // Group message with SELF_CHAT_ALLOW_GROUPS: skip allowlist check,
          // let Python gateway handle group_policy + mention filtering
        } else {
          const isTrustedGroup = isGroup && TRUSTED_GROUPS.has(chatId);
          if (!isTrustedGroup && !matchesAllowedUser(senderId, ALLOWED_USERS, SESSION_DIR)) {
            try {
              console.log(
                JSON.stringify({
                  event: 'ignored',
                  reason: 'allowlist_mismatch',
                  chatId,
                  senderId,
                }),
              );
            } catch {}
            continue;
          }
        }
      }

      const messageContent = getMessageContent(msg);
      const contextInfo = getContextInfo(messageContent);
      const mentionedIds = Array.from(
        new Set((contextInfo?.mentionedJid || []).map(normalizeWhatsAppId).filter(Boolean)),
      );
      const quotedMessageId = contextInfo?.stanzaId || null;
      const quotedParticipant = normalizeWhatsAppId(contextInfo?.participant || '') || null;
      const quotedRemoteJid = normalizeWhatsAppId(contextInfo?.remoteJid || '') || null;
      const hasQuotedMessage = !!contextInfo?.quotedMessage;

      // Extract message body
      let body = '';
      let hasMedia = false;
      let mediaType = '';
      const mediaUrls = [];

      if (messageContent.conversation) {
        body = messageContent.conversation;
      } else if (messageContent.extendedTextMessage?.text) {
        body = messageContent.extendedTextMessage.text;
      } else if (messageContent.imageMessage) {
        body = messageContent.imageMessage.caption || '';
        hasMedia = true;
        mediaType = 'image';
        try {
          const buf = await downloadMediaMessage(
            msg,
            'buffer',
            {},
            { logger, reuploadRequest: sock.updateMediaMessage },
          );
          const mime = messageContent.imageMessage.mimetype || 'image/jpeg';
          const extMap = {
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'image/webp': '.webp',
            'image/gif': '.gif',
          };
          const ext = extMap[mime] || '.jpg';
          mkdirSync(IMAGE_CACHE_DIR, { recursive: true });
          const filePath = path.join(
            IMAGE_CACHE_DIR,
            `img_${randomBytes(6).toString('hex')}${ext}`,
          );
          writeFileSync(filePath, buf);
          mediaUrls.push(filePath);
          _tagMediaOwner(filePath, chatId);
        } catch (err) {
          console.error('[bridge] Failed to download image:', err.message);
        }
      } else if (messageContent.videoMessage) {
        body = messageContent.videoMessage.caption || '';
        hasMedia = true;
        mediaType = 'video';
        try {
          const buf = await downloadMediaMessage(
            msg,
            'buffer',
            {},
            { logger, reuploadRequest: sock.updateMediaMessage },
          );
          const mime = messageContent.videoMessage.mimetype || 'video/mp4';
          const ext = mime.includes('mp4') ? '.mp4' : '.mkv';
          mkdirSync(DOCUMENT_CACHE_DIR, { recursive: true });
          const filePath = path.join(
            DOCUMENT_CACHE_DIR,
            `vid_${randomBytes(6).toString('hex')}${ext}`,
          );
          writeFileSync(filePath, buf);
          mediaUrls.push(filePath);
          _tagMediaOwner(filePath, chatId);
        } catch (err) {
          console.error('[bridge] Failed to download video:', err.message);
        }
      } else if (messageContent.audioMessage || messageContent.pttMessage) {
        hasMedia = true;
        mediaType = messageContent.pttMessage ? 'ptt' : 'audio';
        try {
          const audioMsg = messageContent.pttMessage || messageContent.audioMessage;
          const buf = await downloadMediaMessage(
            msg,
            'buffer',
            {},
            { logger, reuploadRequest: sock.updateMediaMessage },
          );
          const mime = audioMsg.mimetype || 'audio/ogg';
          const ext = mime.includes('ogg') ? '.ogg' : mime.includes('mp4') ? '.m4a' : '.ogg';
          mkdirSync(AUDIO_CACHE_DIR, { recursive: true });
          const filePath = path.join(
            AUDIO_CACHE_DIR,
            `aud_${randomBytes(6).toString('hex')}${ext}`,
          );
          writeFileSync(filePath, buf);
          mediaUrls.push(filePath);
          _tagMediaOwner(filePath, chatId);
        } catch (err) {
          console.error('[bridge] Failed to download audio:', err.message);
        }
      } else if (messageContent.documentMessage) {
        body = messageContent.documentMessage.caption || '';
        hasMedia = true;
        mediaType = 'document';
        const fileName = messageContent.documentMessage.fileName || 'document';
        try {
          const buf = await downloadMediaMessage(
            msg,
            'buffer',
            {},
            { logger, reuploadRequest: sock.updateMediaMessage },
          );
          mkdirSync(DOCUMENT_CACHE_DIR, { recursive: true });
          const safeFileName = path.basename(fileName).replace(/[^a-zA-Z0-9._-]/g, '_');
          const filePath = path.join(
            DOCUMENT_CACHE_DIR,
            `doc_${randomBytes(6).toString('hex')}_${safeFileName}`,
          );
          writeFileSync(filePath, buf);
          mediaUrls.push(filePath);
          _tagMediaOwner(filePath, chatId);
        } catch (err) {
          console.error('[bridge] Failed to download document:', err.message);
        }
      }

      // Extract image from quoted/forwarded message so Viko can see it
      if (contextInfo?.quotedMessage?.imageMessage) {
        const quotedImgMsg = contextInfo.quotedMessage.imageMessage;
        try {
          const fakeMsg = {
            key: {
              remoteJid: quotedRemoteJid || chatId,
              id: quotedMessageId,
              participant: quotedParticipant || undefined,
              fromMe: false,
            },
            message: contextInfo.quotedMessage,
          };
          const buf = await downloadMediaMessage(
            fakeMsg,
            'buffer',
            {},
            { logger, reuploadRequest: sock.updateMediaMessage },
          );
          const mime = quotedImgMsg.mimetype || 'image/jpeg';
          const extMap = {
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'image/webp': '.webp',
            'image/gif': '.gif',
          };
          const ext = extMap[mime] || '.jpg';
          mkdirSync(IMAGE_CACHE_DIR, { recursive: true });
          const filePath = path.join(
            IMAGE_CACHE_DIR,
            `quoted_${randomBytes(6).toString('hex')}${ext}`,
          );
          writeFileSync(filePath, buf);
          mediaUrls.push(filePath);
          _tagMediaOwner(filePath, chatId);
          if (!hasMedia) {
            hasMedia = true;
            mediaType = 'image';
          }
        } catch (err) {
          console.error('[bridge] Failed to download quoted image:', err.message);
        }
      }

      // Extract document from a quoted/forwarded message so Viko can read/convert it
      // (e.g. user replies to a .docx with "buatin pdf"). Without this only the text
      // "[dokumen: name]" reaches Viko — the file itself never arrives.
      if (contextInfo?.quotedMessage?.documentMessage) {
        const quotedDocMsg = contextInfo.quotedMessage.documentMessage;
        try {
          const fakeMsg = {
            key: {
              remoteJid: quotedRemoteJid || chatId,
              id: quotedMessageId,
              participant: quotedParticipant || undefined,
              fromMe: false,
            },
            message: contextInfo.quotedMessage,
          };
          const buf = await downloadMediaMessage(
            fakeMsg,
            'buffer',
            {},
            { logger, reuploadRequest: sock.updateMediaMessage },
          );
          const fileName = quotedDocMsg.fileName || 'document';
          mkdirSync(DOCUMENT_CACHE_DIR, { recursive: true });
          const safeFileName = path.basename(fileName).replace(/[^a-zA-Z0-9._-]/g, '_');
          const filePath = path.join(
            DOCUMENT_CACHE_DIR,
            `quoted_${randomBytes(6).toString('hex')}_${safeFileName}`,
          );
          writeFileSync(filePath, buf);
          mediaUrls.push(filePath);
          _tagMediaOwner(filePath, chatId);
          if (!hasMedia) {
            hasMedia = true;
            mediaType = 'document';
          }
        } catch (err) {
          console.error('[bridge] Failed to download quoted document:', err.message);
        }
      }

      // Extract text from quoted/replied message so Viko knows what's being replied to
      if (hasQuotedMessage && contextInfo?.quotedMessage) {
        const qm = contextInfo.quotedMessage;
        const quotedText =
          qm.conversation ||
          qm.extendedTextMessage?.text ||
          qm.imageMessage?.caption ||
          qm.videoMessage?.caption ||
          qm.documentMessage?.caption ||
          (qm.audioMessage ? '[pesan suara]' : null) ||
          (qm.imageMessage ? '[gambar]' : null) ||
          (qm.videoMessage ? '[video]' : null) ||
          (qm.documentMessage ? `[dokumen: ${qm.documentMessage.fileName || 'file'}]` : null);
        if (quotedText) {
          const quotedFrom = quotedParticipant ? quotedParticipant.split('@')[0] : 'unknown';
          body = `[Reply to: "${quotedText}" — from ${quotedFrom}]\n${body}`;
        }
      }

      // For media without caption, use a placeholder so the API message is never empty
      if (hasMedia && !body) {
        body = `[${mediaType} received]`;
      }

      // Ignore Hermes' own reply messages in self-chat mode to avoid loops.
      if (
        msg.key.fromMe &&
        ((REPLY_PREFIX && body.startsWith(REPLY_PREFIX)) || recentlySentIds.has(msg.key.id))
      ) {
        if (WHATSAPP_DEBUG) {
          try {
            console.log(
              JSON.stringify({
                event: 'ignored',
                reason: 'agent_echo',
                chatId,
                messageId: msg.key.id,
              }),
            );
          } catch {}
        }
        continue;
      }

      // Skip empty messages
      if (!body && !hasMedia) {
        if (WHATSAPP_DEBUG) {
          try {
            console.log(
              JSON.stringify({
                event: 'ignored',
                reason: 'empty',
                chatId,
                messageKeys: Object.keys(msg.message || {}),
              }),
            );
          } catch (err) {
            console.error('Failed to log empty message event:', err);
          }
        }
        continue;
      }

      // Resolve owner ONCE (handles LID↔phone via session mapping files). Reused by the
      // read-only tag and the scope stamp, and logged so a mis-detected owner is visible.
      const isOwner =
        !msg.key.fromMe &&
        OWNER_PHONES.size > 0 &&
        matchesAllowedUser(senderId, OWNER_PHONES, SESSION_DIR);

      // SECURITY (B1): only the owner may clear a dangerous-command approval gate (or
      // /yolo past all gates). Group sessions are per-user, so a non-owner's bare
      // "approve"/"yes"/"ok"/"confirm"/"/yolo" would clear THEIR OWN pending gate —
      // letting any member execute a command they themselves triggered. The gateway only
      // consumes these literal tokens, so dropping them from non-owners (deterministically,
      // by the bridge's unspoofable owner check) keeps a member-triggered dangerous command
      // gated forever (never approved -> never runs). Owner approvals pass untouched;
      // "deny"/"no" are allowed (denying is safe). Only a lone token is matched, so normal
      // chatter ("ok siap, viko ...") is unaffected.
      if (isGroup && !isOwner && !msg.key.fromMe) {
        const _tok = body.trim().toLowerCase().replace(/^\//, '');
        if (['approve', 'yes', 'ok', 'confirm', 'yolo'].includes(_tok)) {
          try {
            console.log(
              JSON.stringify({
                event: 'ignored',
                reason: 'non_owner_approval_blocked',
                chatId,
                senderId,
                token: _tok,
              }),
            );
          } catch {}
          _securityLog(`non_owner_approval_blocked chatId=${chatId} senderId=${senderId} token=${_tok}`);
          continue;
        }
      }

      // Tag group messages from non-owner members so the gateway enforces read-only mode.
      // Owner is identified by WHATSAPP_HOME_CHANNEL. Non-owners can ask questions and
      // check data, but cannot authorize execution, deploys, or infra changes.
      if (!msg.key.fromMe && isGroup && OWNER_PHONES.size > 0 && !isOwner) {
        body = `[READ-ONLY MEMBER - hanya boleh tanya dan cek data, tidak bisa authorize execution]\n${body}`;
      }

      // Deterministic, unspoofable scope stamp. Binds each message to its project
      // (group JID → routing.json slug) and flags whether the sender is the owner —
      // so the gateway scopes replies and gates the cross-project catalog WITHOUT
      // guessing. Covers DMs + unregistered groups (the gaps a rule alone can't close).
      if (!msg.key.fromMe) {
        const proj = !isGroup ? 'DM' : _jidToSlug[chatId] || 'UNREGISTERED';
        // For unregistered groups, include the JID so admin Hermes can pass it to add-project.py
        const jidField = proj === 'UNREGISTERED' && isGroup ? ` jid=${chatId}` : '';
        // Sender identity so the agent addresses the RIGHT person by name instead of
        // guessing/bleeding a name from history. Owner -> VIKO_OWNER_NAME; members ->
        // their pushName (or a name learned from earlier messages), else the number.
        // Strip brackets/newlines so a crafted pushName can't break out of the CTX tag.
        const senderLabel =
          (isOwner
            ? process.env.VIKO_OWNER_NAME || senderNumber
            : msg.pushName || _nameByNumber[senderNumber] || senderNumber
          )
            .replace(/[[\]\n]/g, '')
            .trim() || senderNumber;
        body = `[CTX project=${proj}${jidField} caller=${isOwner ? 'owner' : 'member'} sender=${senderLabel}]\n${body}`;
        // Inbound ops log (sender identity + resolved owner) → FILE, because the bridge's
        // runtime stdout isn't captured by docker logs. Lets us debug owner mis-detection.
        try {
          appendFileSync(
            '/opt/data/logs/bridge-inbound.log',
            JSON.stringify({
              t: new Date().toISOString(),
              chatId,
              senderId,
              owner: isOwner,
              group: isGroup,
              proj,
            }) + '\n',
          );
        } catch {}
      }

      // Append @mentioned phone numbers so Viko can act on them
      // e.g. "allow @X to DM" — Viko reads the phone from [Mentioned: ...]
      const humanMentions = mentionedIds
        .filter((id) => !botIds.includes(id))
        .map((id) => id.split('@')[0]);
      if (humanMentions.length > 0) {
        body = `${body}\n[Mentioned: ${humanMentions.join(', ')}]`;
      }

      // Recent-media context: remember the last file per chat, and when a Viko-directed
      // message has no media of its own, staple on a file sent moments ago in a separate
      // message (e.g. forward a .docx, then "buatin pdf viko"). Gated to Viko mentions +
      // a short window and consumed once, so stale files aren't stapled onto chatter.
      const _mentionsViko =
        /\bviko\b/i.test(body) || mentionedIds.some((id) => botIds.includes(id));
      if (mediaUrls.length > 0) {
        _recentMediaByChat[chatId] = { paths: mediaUrls.slice(), type: mediaType, ts: Date.now() };
      } else if (_mentionsViko) {
        const _recent = _recentMediaByChat[chatId];
        if (_recent && Date.now() - _recent.ts < RECENT_MEDIA_WINDOW_MS) {
          mediaUrls.push(..._recent.paths);
          hasMedia = true;
          mediaType = _recent.type;
          const _names = _recent.paths.map((p) => path.basename(p)).join(', ');
          body = `[Lampiran dari pesan sebelumnya di chat ini ikut disertakan: ${_names}]\n${body}`;
          delete _recentMediaByChat[chatId];
        }
      }

      const event = {
        messageId: msg.key.id,
        chatId,
        senderId,
        senderName: msg.pushName || senderNumber,
        chatName: isGroup ? chatId.split('@')[0] : msg.pushName || senderNumber,
        isGroup,
        body,
        hasMedia,
        mediaType,
        mediaUrls,
        mentionedIds,
        quotedMessageId,
        quotedParticipant,
        quotedRemoteJid,
        hasQuotedMessage,
        botIds,
        timestamp: msg.messageTimestamp,
      };

      // A group message is "directed at Viko" if it mentions "viko"/@Viko OR replies
      // to one of Viko's own messages. Computed once and reused by both the registered
      // (E2 media gate) and unregistered branches.
      const _isReplyToViko =
        hasQuotedMessage && !!quotedParticipant && botIds.includes(quotedParticipant);

      const _targetPort = _routing[chatId];
      if (_targetPort) {
        // E2: an undirected group message gets dropped by the project's require_mention
        // anyway, so don't waste a queue slot on it (all media has already been downloaded
        // and cached above — including the recent-media stapling cache — so 'forward a
        // file, then "viko buatin pdf"' still works on the NEXT, directed message). Owner
        // messages and DMs are never gated here; only skip the QUEUE PUSH for undirected
        // group msgs. Directed messages keep their media and are pushed normally.
        if (isGroup && !isOwner && !_mentionsViko && !_isReplyToViko) {
          try {
            console.log(
              JSON.stringify({
                event: 'ignored',
                reason: 'group_not_directed_at_viko',
                chatId,
                senderId,
                port: _targetPort,
              }),
            );
          } catch {}
          _securityLog(
            `group_not_directed_at_viko chatId=${chatId} senderId=${senderId} port=${_targetPort}`,
          );
          continue;
        }
        const _pq = (messageQueues[String(_targetPort)] = messageQueues[String(_targetPort)] || []);
        _pq.push(event);
        if (_pq.length > MAX_QUEUE_SIZE) _pq.shift();
      } else {
        // Unregistered group: only forward if the message is directed at Viko —
        // it mentions "viko"/@Viko, OR it's a reply to one of Viko's own messages.
        // Casual chatter to other members is silently dropped. No time-based session:
        // a blanket "all owner messages for N minutes" window caught unrelated talk
        // (owner saying "viko" once made Viko butt into every later message).
        // DMs always pass through (isGroup=false).
        if (!isGroup || _mentionsViko || _isReplyToViko) {
          globalQueue.push(event);
          if (globalQueue.length > MAX_QUEUE_SIZE) globalQueue.shift();
          // Backward compat: also push to legacy messageQueue (Admin Hermes uses this)
          messageQueue.push(event);
          if (messageQueue.length > MAX_QUEUE_SIZE) messageQueue.shift();
        } else {
          try {
            console.log(
              JSON.stringify({
                event: 'ignored',
                reason: 'group_not_directed_at_viko',
                chatId,
                senderId,
              }),
            );
          } catch {}
          _securityLog(`group_not_directed_at_viko chatId=${chatId} senderId=${senderId}`);
        }
      }
    }
  });
}

// HTTP server
const app = express();
// Relay containers ship outbound files to admin as base64 in the JSON body. WhatsApp
// media caps at ~64MB → ~85MB once base64-inflated, and Express defaults to a 100kb
// body limit — so any file over ~75kb would 413 here and surface to the relay as a
// generic 503. Lift the ceiling so real documents/videos get through.
app.use(express.json({ limit: '100mb' }));

if (RELAY_MODE) {
  // Relay mode: proxy all requests to the admin bridge, filtered by port

  // Forward an upstream response preserving its REAL status. `await resp.json()` throws
  // when admin returns a non-JSON error body (e.g. a 413 on an oversized payload), and
  // the surrounding catch would then mask it as a generic 503 — hiding the true cause.
  // Read as text and parse defensively so the actual status/detail reaches the caller.
  async function _forwardRelay(res, resp) {
    const text = await resp.text();
    let body;
    try {
      body = text ? JSON.parse(text) : {};
    } catch {
      body = { error: 'relay_upstream', status: resp.status, detail: text.slice(0, 500) };
    }
    res.status(resp.status).json(body);
  }

  // The admin downloads inbound media to absolute paths under its own cache dirs,
  // which this isolated container can't read — and Hermes' SSRF guard blocks the
  // loopback HTTP fallback. So pull each referenced file from the admin's /media
  // endpoint and write it to the SAME absolute path here, making Hermes'
  // os.path.isabs media branch resolve it locally. Best-effort + idempotent
  // (skips files already cached). Runs at the /messages boundary.
  async function _prefetchRelayMedia(messages) {
    if (!Array.isArray(messages)) return messages;
    for (const msg of messages) {
      const urls = (msg && msg.mediaUrls) || [];
      for (const p of urls) {
        try {
          if (typeof p !== 'string' || !path.isAbsolute(p) || existsSync(p)) continue;
          const r = await fetch(`${RELAY_TARGET}/media/${encodeURIComponent(path.basename(p))}`, {
            headers: _relayHeaders(),
          });
          if (!r.ok) {
            console.log(`[bridge] relay media prefetch ${r.status} for ${path.basename(p)}`);
            continue;
          }
          mkdirSync(path.dirname(p), { recursive: true });
          writeFileSync(p, Buffer.from(await r.arrayBuffer()));
          console.log(`[bridge] relay prefetched media → ${p}`);
        } catch (e) {
          console.log(`[bridge] relay media prefetch failed: ${e.message}`);
        }
      }
    }
    return messages;
  }

  app.get('/messages', async (req, res) => {
    try {
      const url = PORT_FILTER
        ? `${RELAY_TARGET}/messages?port=${PORT_FILTER}`
        : `${RELAY_TARGET}/messages`;
      const resp = await fetch(url, { headers: _relayHeaders() });
      res.json(await _prefetchRelayMedia(await resp.json()));
    } catch {
      res.json([]);
    }
  });
  app.post('/send', async (req, res) => {
    try {
      const resp = await fetch(`${RELAY_TARGET}/send`, {
        method: 'POST',
        headers: _relayHeaders(),
        body: JSON.stringify(req.body),
      });
      await _forwardRelay(res, resp);
    } catch (e) {
      res.status(503).json({ error: 'relay_error', detail: e.message });
    }
  });
  app.post('/send-media', async (req, res) => {
    try {
      let payload = req.body;
      const fp = payload && payload.filePath;
      // The admin can't read this isolated container's filesystem (e.g. files under
      // /opt/data/cache or this project's own dirs), so ship the BYTES instead of a
      // path it can't open. Admin materializes them to a temp file and sends.
      if (fp && path.isAbsolute(fp) && existsSync(fp)) {
        payload = {
          chatId: payload.chatId,
          mediaType: payload.mediaType,
          caption: payload.caption,
          fileName: payload.fileName || path.basename(fp),
          fileBase64: readFileSync(fp).toString('base64'),
        };
      }
      const resp = await fetch(`${RELAY_TARGET}/send-media`, {
        method: 'POST',
        headers: _relayHeaders(),
        body: JSON.stringify(payload),
      });
      await _forwardRelay(res, resp);
    } catch (e) {
      res.status(503).json({ error: 'relay_error', detail: e.message });
    }
  });
  app.post('/edit', async (req, res) => {
    try {
      const resp = await fetch(`${RELAY_TARGET}/edit`, {
        method: 'POST',
        headers: _relayHeaders(),
        body: JSON.stringify(req.body),
      });
      await _forwardRelay(res, resp);
    } catch (e) {
      res.status(503).json({ error: 'relay_error', detail: e.message });
    }
  });
  ['post'].forEach((m) =>
    app[m]('/typing', async (req, res) => {
      try {
        await fetch(`${RELAY_TARGET}/typing`, {
          method: 'POST',
          headers: _relayHeaders(),
          body: JSON.stringify(req.body),
        });
        res.json({ ok: true });
      } catch {
        res.json({ ok: false });
      }
    }),
  );
  app.get('/health', async (req, res) => {
    try {
      const resp = await fetch(`${RELAY_TARGET}/health`, {
        headers: _relayHeaders(),
      });
      const data = /** @type {Record<string, unknown>} */ (await resp.json());
      res.json({ ...data, relay: true, port_filter: PORT_FILTER });
    } catch {
      res.json({ status: 'relay_disconnected', relay: true });
    }
  });
  app.get('/chat/:id', async (req, res) => {
    try {
      const resp = await fetch(`${RELAY_TARGET}/chat/${req.params.id}`, {
        headers: _relayHeaders(),
      });
      await _forwardRelay(res, resp);
    } catch {
      res.status(503).json({ error: 'relay_error' });
    }
  });
  // Proxy media fetches to the admin (which downloaded the file). Lets this
  // isolated container's vision tool read images/docs it can't access on disk.
  app.get('/media/:file', async (req, res) => {
    try {
      const resp = await fetch(
        `${RELAY_TARGET}/media/${encodeURIComponent(path.basename(req.params.file))}`,
        { headers: _relayHeaders() },
      );
      if (!resp.ok) return res.status(resp.status).json({ error: 'media_relay_error' });
      res.set('Content-Type', resp.headers.get('content-type') || 'application/octet-stream');
      res.send(Buffer.from(await resp.arrayBuffer()));
    } catch {
      res.status(503).json({ error: 'relay_error' });
    }
  });
  const BRIDGE_BIND = process.env.BRIDGE_BIND || '127.0.0.1';
  app.listen(PORT, BRIDGE_BIND, () => {
    console.log(`[bridge] Relay mode → ${RELAY_TARGET} (port_filter: ${PORT_FILTER || 'none'})`);
  });
  // In relay mode, don't start WA socket at all — exit main flow here
} else {
  // Host-header validation — defends against DNS rebinding.
  // The bridge binds loopback-only (127.0.0.1) but a victim browser on
  // the same machine could be tricked into fetching from an attacker
  // hostname that TTL-flips to 127.0.0.1. Reject any request whose Host
  // header doesn't resolve to a loopback alias.
  // See GHSA-ppp5-vxwm-4cf7.
  const _ACCEPTED_HOST_VALUES = new Set([
    'localhost',
    '127.0.0.1',
    '[::1]',
    '::1',
    'viko-hermes-admin', // Docker service name for inter-container access
    ...(process.env.BRIDGE_EXTRA_HOSTS || '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean),
  ]);

  app.use((req, res, next) => {
    const raw = (req.headers.host || '').trim();
    if (!raw) {
      return res.status(400).json({ error: 'Missing Host header' });
    }
    // Strip port suffix: "localhost:3000" → "localhost"
    const hostOnly = (raw.includes(':') ? raw.substring(0, raw.lastIndexOf(':')) : raw)
      .replace(/^\[|\]$/g, '')
      .toLowerCase();
    if (!_ACCEPTED_HOST_VALUES.has(hostOnly)) {
      return res.status(400).json({
        error: 'Invalid Host header. Bridge accepts loopback hosts only.',
      });
    }
    next();
  });

  // ── Outbound scope enforcement (surface #1) ─────────────────────────────────
  // Authorization is server-side, never a container's self-claim. A project relay
  // presents Authorization: Bearer <relay_token>; the admin maps token → the one
  // JID it may send to. Loopback callers (the admin Hermes itself, which posts to
  // 127.0.0.1) carry no token and get full access. A networked caller with no /
  // unknown token is denied (default-deny) — this is the only thing that stops a
  // project container from POSTing /send with another group's chatId.
  function _bearer(req) {
    const m = (req.headers['authorization'] || '').match(/^Bearer\s+(.+)$/i);
    return m ? m[1].trim() : '';
  }
  function _isLoopback(req) {
    const a = req.socket.remoteAddress || '';
    return a === '127.0.0.1' || a === '::1' || a === '::ffff:127.0.0.1';
  }
  function _scopeError(req, chatId) {
    const token = _bearer(req);
    if (token) {
      const jid = _tokenToJid[token];
      if (!jid) return { code: 403, error: 'unknown_relay_token' };
      if (!chatId || chatId !== jid) {
        return { code: 403, error: 'cross_project_send_blocked', allowed: jid };
      }
      return null; // scoped, destination matches
    }
    if (_isLoopback(req)) return null; // admin Hermes (loopback) — full access
    return { code: 403, error: 'relay_token_required' };
  }

  const _SCOPED_PATHS = new Set(['/send', '/send-media', '/edit', '/typing']);
  app.use((req, res, next) => {
    if (req.method === 'POST' && _SCOPED_PATHS.has(req.path)) {
      const chatId = (req.body && req.body.chatId) || '';
      const err = _scopeError(req, chatId);
      if (err) {
        const _msg = `scope-deny ${req.path} chatId=${chatId || '?'} (${err.error}${err.allowed ? ' allowed=' + err.allowed : ''})`;
        console.warn(`[bridge] ${_msg}`);
        _securityLog(_msg);
        return res.status(err.code).json(err);
      }
    }
    next();
  });

  // Relay scope introspection — a project relay (or the boot guard) presents its
  // token and gets back the exact port + JID(s) it is allowed to talk to. Used to
  // self-verify isolation without spraying a canary message into a group.
  app.get('/relay/scope', (req, res) => {
    const token = _bearer(req);
    const jid = _tokenToJid[token];
    if (!jid) return res.status(403).json({ error: 'unknown_relay_token' });
    res.json({ port: _routing[jid], allowed_jids: [jid] });
  });

  // Poll for new messages — ?port=8101 for project instances, no param for Admin Hermes
  app.get('/messages', (req, res) => {
    // Scope reads (A1): /messages destructively drains a per-port queue. A networked
    // (non-loopback) caller must present a valid relay token; the port it may drain is
    // FORCED to the one bound to its JID — it cannot pass an arbitrary ?port to read
    // (and drain) another project's queue. Loopback (admin Hermes) keeps full access
    // and the historical ?port behavior.
    if (!_isLoopback(req)) {
      const token = _bearer(req);
      const jid = token ? _tokenToJid[token] : '';
      if (!jid) {
        const _m = `scope-deny GET /messages (${token ? 'unknown_relay_token' : 'relay_token_required'})`;
        console.warn(`[bridge] ${_m}`);
        _securityLog(_m);
        return res
          .status(403)
          .json({ error: token ? 'unknown_relay_token' : 'relay_token_required' });
      }
      const allowedPort = _routing[jid] != null ? String(_routing[jid]) : null;
      if (!allowedPort) {
        const _m = `scope-deny GET /messages (no_port_for_jid) jid=${jid}`;
        console.warn(`[bridge] ${_m}`);
        _securityLog(_m);
        return res.status(403).json({ error: 'no_port_for_jid', allowed: jid });
      }
      const requested = req.query.port ? String(req.query.port) : null;
      if (requested && requested !== allowedPort) {
        const _m = `scope-deny GET /messages (cross_project_read_blocked) requested=${requested} allowed=${allowedPort}`;
        console.warn(`[bridge] ${_m}`);
        _securityLog(_m);
        return res
          .status(403)
          .json({ error: 'cross_project_read_blocked', allowed_port: allowedPort });
      }
      const q = messageQueues[allowedPort] || [];
      const msgs = q.splice(0, q.length);
      messageQueues[allowedPort] = [];
      return res.json(msgs);
    }
    const port = req.query.port ? String(req.query.port) : null;
    if (port) {
      const q = messageQueues[port] || [];
      const msgs = q.splice(0, q.length);
      messageQueues[port] = [];
      res.json(msgs);
    } else {
      // Admin Hermes: gets unrouted messages (globalQueue) + legacy messageQueue
      const msgs = [
        ...messageQueue.splice(0, messageQueue.length),
        ...globalQueue.splice(0, globalQueue.length),
      ];
      // Deduplicate by messageId in case of overlap
      const seen = new Set();
      res.json(
        msgs.filter((m) => {
          if (seen.has(m.messageId)) return false;
          seen.add(m.messageId);
          return true;
        }),
      );
    }
  });

  // Send a message
  app.post('/send', async (req, res) => {
    if (!sock || connectionState !== 'connected') {
      return res.status(503).json({ error: 'Not connected to WhatsApp' });
    }

    const { chatId, message } = req.body;
    if (!chatId || !message) {
      return res.status(400).json({ error: 'chatId and message are required' });
    }

    try {
      const chunks = splitLongMessage(formatOutgoingMessage(message));
      const messageIds = [];
      for (let i = 0; i < chunks.length; i += 1) {
        const sent = await sendWithTimeout(chatId, { text: chunks[i] });
        trackSentMessageId(sent);
        if (sent?.key?.id) messageIds.push(sent.key.id);
        if (chunks.length > 1 && i < chunks.length - 1) {
          await sleep(CHUNK_DELAY_MS);
        }
      }

      res.json({
        success: true,
        messageId: messageIds[messageIds.length - 1],
        messageIds,
      });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  // Edit a previously sent message
  app.post('/edit', async (req, res) => {
    if (!sock || connectionState !== 'connected') {
      return res.status(503).json({ error: 'Not connected to WhatsApp' });
    }

    const { chatId, messageId, message } = req.body;
    if (!chatId || !messageId || !message) {
      return res.status(400).json({ error: 'chatId, messageId, and message are required' });
    }

    try {
      const key = { id: messageId, fromMe: true, remoteJid: chatId };
      const chunks = splitLongMessage(formatOutgoingMessage(message));
      const messageIds = [];

      await sendWithTimeout(chatId, { text: chunks[0], edit: key });
      if (chunks.length > 1) {
        for (let i = 1; i < chunks.length; i += 1) {
          const sent = await sendWithTimeout(chatId, { text: chunks[i] });
          trackSentMessageId(sent);
          if (sent?.key?.id) messageIds.push(sent.key.id);
          if (i < chunks.length - 1) {
            await sleep(CHUNK_DELAY_MS);
          }
        }
      }

      res.json({ success: true, messageIds });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  // MIME type map and media type inference for /send-media
  const MIME_MAP = {
    jpg: 'image/jpeg',
    jpeg: 'image/jpeg',
    png: 'image/png',
    webp: 'image/webp',
    gif: 'image/gif',
    mp4: 'video/mp4',
    mov: 'video/quicktime',
    avi: 'video/x-msvideo',
    mkv: 'video/x-matroska',
    '3gp': 'video/3gpp',
    pdf: 'application/pdf',
    doc: 'application/msword',
    docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  };

  function inferMediaType(ext) {
    if (['jpg', 'jpeg', 'png', 'webp', 'gif'].includes(ext)) return 'image';
    if (['mp4', 'mov', 'avi', 'mkv', '3gp'].includes(ext)) return 'video';
    if (['ogg', 'opus', 'mp3', 'wav', 'm4a'].includes(ext)) return 'audio';
    return 'document';
  }

  // Send media (image, video, document) natively
  app.post('/send-media', async (req, res) => {
    if (!sock || connectionState !== 'connected') {
      return res.status(503).json({ error: 'Not connected to WhatsApp' });
    }

    let { chatId, filePath, mediaType, caption, fileName, fileBase64 } = req.body;
    // Relay containers ship file BYTES (their isolated filesystem is unreadable here),
    // so materialize them to a temp file and let the path-based logic below run as-is.
    if (fileBase64 && !filePath) {
      try {
        mkdirSync(DOCUMENT_CACHE_DIR, { recursive: true });
        const safe = path.basename(fileName || 'file').replace(/[^a-zA-Z0-9._-]/g, '_');
        filePath = path.join(
          DOCUMENT_CACHE_DIR,
          `outbox_${randomBytes(6).toString('hex')}_${safe}`,
        );
        writeFileSync(filePath, Buffer.from(fileBase64, 'base64'));
      } catch (e) {
        return res.status(500).json({ error: 'outbox write failed: ' + e.message });
      }
    }
    if (!chatId || !filePath) {
      return res.status(400).json({ error: 'chatId and filePath are required' });
    }

    // Block GIF files — use send_browser_video MCP tool instead
    if (filePath.toLowerCase().endsWith('.gif')) {
      return res.status(415).json({
        error:
          'GIF not supported for video delivery. Use the send_browser_video MCP tool to send browser recordings as MP4.',
        hint: 'send_browser_video(chat_id, caption) — finds latest webm recording and converts to mp4 automatically.',
      });
    }

    try {
      if (!existsSync(filePath)) {
        return res.status(404).json({ error: `File not found: ${filePath}` });
      }

      // Drop a duplicate send (gateway MEDIA: delivery + viko-media-autosend hook can both
      // fire for the same file) within the window, keyed by chat + name + size.
      const _dkey = `${chatId}|${path.basename(fileName || filePath)}|${statSync(filePath).size}`;
      const _nowSend = Date.now();
      if (_recentSends[_dkey] && _nowSend - _recentSends[_dkey] < SEND_DEDUP_MS) {
        return res.json({ success: true, deduped: true });
      }
      _recentSends[_dkey] = _nowSend;

      const buffer = readFileSync(filePath);
      const ext = filePath.toLowerCase().split('.').pop();
      const type = mediaType || inferMediaType(ext);
      let msgPayload;

      switch (type) {
        case 'image':
          msgPayload = {
            image: buffer,
            caption: caption || undefined,
            mimetype: MIME_MAP[ext] || 'image/jpeg',
          };
          break;
        case 'video':
          msgPayload = {
            video: buffer,
            caption: caption || undefined,
            mimetype: MIME_MAP[ext] || 'video/mp4',
          };
          break;
        case 'audio': {
          // WhatsApp only renders a native voice bubble (ptt) when the file is ogg/opus.
          // If the caller passes mp3, wav, m4a etc. (e.g. from Edge TTS / NeuTTS),
          // silently convert to ogg/opus via ffmpeg so ptt is always honoured.
          let audioBuffer = buffer;
          let audioExt = ext;
          const needsConversion = !['ogg', 'opus'].includes(ext);
          let tmpPath = null;
          if (needsConversion) {
            tmpPath = path.join(tmpdir(), `hermes_voice_${randomBytes(6).toString('hex')}.ogg`);
            try {
              execSync(
                `ffmpeg -y -i ${JSON.stringify(filePath)} -ar 48000 -ac 1 -c:a libopus ${JSON.stringify(tmpPath)}`,
                { timeout: 30000, stdio: 'pipe' },
              );
              audioBuffer = readFileSync(tmpPath);
              audioExt = 'ogg';
            } catch (convErr) {
              // ffmpeg not available or conversion failed — fall back to original format
              console.warn(
                '[bridge] ffmpeg conversion failed, sending as file attachment:',
                convErr.message,
              );
            } finally {
              try {
                if (tmpPath && existsSync(tmpPath)) unlinkSync(tmpPath);
              } catch (_) {}
            }
          }
          const audioMime =
            audioExt === 'ogg' || audioExt === 'opus' ? 'audio/ogg; codecs=opus' : 'audio/mpeg';
          msgPayload = {
            audio: audioBuffer,
            mimetype: audioMime,
            ptt: audioExt === 'ogg' || audioExt === 'opus',
          };
          break;
        }
        case 'document':
        default:
          msgPayload = {
            document: buffer,
            fileName: fileName || path.basename(filePath),
            caption: caption || undefined,
            mimetype: MIME_MAP[ext] || 'application/octet-stream',
          };
          break;
      }

      const sent = await sendWithTimeout(chatId, msgPayload);

      trackSentMessageId(sent);

      res.json({ success: true, messageId: sent?.key?.id });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  // Typing indicator
  app.post('/typing', async (req, res) => {
    if (!sock || connectionState !== 'connected') {
      return res.status(503).json({ error: 'Not connected' });
    }

    const { chatId } = req.body;
    if (!chatId) return res.status(400).json({ error: 'chatId required' });

    try {
      await sock.sendPresenceUpdate('composing', chatId);
      res.json({ success: true });
    } catch {
      res.json({ success: false });
    }
  });

  // Chat info
  app.get('/chat/:id', async (req, res) => {
    const chatId = req.params.id;
    // Scope reads (A1): a networked caller may only read the chat its token is bound to
    // (the chat id IS the jid). Loopback (admin) keeps full access.
    if (!_isLoopback(req)) {
      const token = _bearer(req);
      const jid = token ? _tokenToJid[token] : '';
      if (!jid || jid !== chatId) {
        console.warn(
          `[bridge] scope-deny GET /chat/${chatId} (${!token ? 'relay_token_required' : !jid ? 'unknown_relay_token' : 'cross_project_read_blocked'})`,
        );
        return res
          .status(403)
          .json({ error: !token ? 'relay_token_required' : !jid ? 'unknown_relay_token' : 'cross_project_read_blocked' });
      }
    }
    const isGroup = chatId.endsWith('@g.us');

    if (isGroup && sock) {
      try {
        const metadata = await sock.groupMetadata(chatId);
        return res.json({
          name: metadata.subject,
          isGroup: true,
          participants: metadata.participants.map((p) => p.id),
        });
      } catch {
        // Fall through to default
      }
    }

    res.json({
      name: chatId.replace(/@.*/, ''),
      isGroup,
      participants: [],
    });
  });

  // Serve a downloaded media file by basename. The relay /messages handler pulls
  // from here to mirror the admin's media into each project container's cache at the
  // same absolute path. basename() guards against path traversal.
  app.get('/media/:file', (req, res) => {
    const file = path.basename(req.params.file);
    // Scope reads (A1): a networked caller must present a valid relay token. When the
    // file is tagged with its owning chat (_mediaOwnerByFile), the token's JID must
    // match — a project relay can only pull its own group's media. Loopback (admin)
    // keeps full access.
    if (!_isLoopback(req)) {
      const token = _bearer(req);
      const jid = token ? _tokenToJid[token] : '';
      if (!jid) {
        console.warn(
          `[bridge] scope-deny GET /media/${file} (${token ? 'unknown_relay_token' : 'relay_token_required'})`,
        );
        return res
          .status(403)
          .json({ error: token ? 'unknown_relay_token' : 'relay_token_required' });
      }
      const owner = _mediaOwnerByFile.get(file);
      // Files written before this map was populated (e.g. across a restart) have no
      // owner entry. A valid token is still required above; we allow the fetch so
      // legitimate cross-restart prefetch keeps working. TODO: persist ownership tags
      // so unknown-owner files can be denied instead of allowed.
      if (owner && owner !== jid) {
        console.warn(
          `[bridge] scope-deny GET /media/${file} (cross_project_media_blocked) owner=${owner} caller=${jid}`,
        );
        return res.status(403).json({ error: 'cross_project_media_blocked' });
      }
    }
    for (const dir of [IMAGE_CACHE_DIR, DOCUMENT_CACHE_DIR, AUDIO_CACHE_DIR]) {
      const fp = path.join(dir, file);
      if (existsSync(fp)) return res.sendFile(fp);
    }
    res.status(404).json({ error: 'media_not_found' });
  });

  // Group participants with names
  app.get('/group/:jid/participants', async (req, res) => {
    const jid = req.params.jid;
    // Scope reads (A1): a networked caller may only enumerate participants of the group
    // its token is bound to (the :jid param). Loopback (admin) keeps full access.
    if (!_isLoopback(req)) {
      const token = _bearer(req);
      const tokenJid = token ? _tokenToJid[token] : '';
      if (!tokenJid || tokenJid !== jid) {
        console.warn(
          `[bridge] scope-deny GET /group/${jid}/participants (${!token ? 'relay_token_required' : !tokenJid ? 'unknown_relay_token' : 'cross_project_read_blocked'})`,
        );
        return res
          .status(403)
          .json({ error: !token ? 'relay_token_required' : !tokenJid ? 'unknown_relay_token' : 'cross_project_read_blocked' });
      }
    }
    if (!jid.endsWith('@g.us') || !sock) {
      return res.status(400).json({ error: 'Not a group JID or socket not ready' });
    }
    try {
      const meta = await sock.groupMetadata(jid);
      // Drop Viko's own account so it never shows as a candidate member and the model
      // never has to guess which number is "itself" (it would otherwise mislabel one).
      const selfIds = new Set(
        [normalizeWhatsAppId(sock.user?.id), normalizeWhatsAppId(sock.user?.lid)].filter(Boolean),
      );
      const participants = meta.participants
        .filter((p) => !selfIds.has(normalizeWhatsAppId(p.id)))
        .map((p) => {
        // WhatsApp now returns participants as @lid (privacy). Resolve to a real phone
        // via the session LID→phone map; fall back to null (NOT the raw LID) so callers
        // never register a LID as if it were a phone number. Names come from pushNames
        // we've observed — unavailable for members who have never sent a message.
        const isLid = p.id.endsWith('@lid');
        const num = p.id.split('@')[0];
        const phone = isLid ? _lidToPhone[num] || null : num;
        const name = _nameByNumber[num] || (phone && _nameByNumber[phone]) || null;
        return {
          jid: p.id,
          lid: isLid ? num : null,
          phone,
          name,
          resolved: !!phone,
          admin: p.admin || null,
        };
      });
      res.json({ group: meta.subject, jid, participants });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  });

  // Health check. Stays open (no token required) so liveness probes work, but
  // non-loopback callers get a minimal payload — the per-port queue map and routing
  // counts are internal topology and must not leak to project relays (A1).
  app.get('/health', (req, res) => {
    if (!_isLoopback(req)) {
      return res.json({ status: connectionState, uptime: process.uptime() });
    }
    res.json({
      status: connectionState,
      queueLength: messageQueue.length + globalQueue.length,
      perPortQueues: Object.fromEntries(
        Object.entries(messageQueues).map(([p, q]) => [p, q.length]),
      ),
      routingEntries: Object.keys(_routing).length,
      uptime: process.uptime(),
    });
  });

  // Start
  if (PAIR_ONLY) {
    // Pair-only mode: just connect, show QR, save creds, exit. No HTTP server.
    console.log('📱 WhatsApp pairing mode');
    console.log(`📁 Session: ${SESSION_DIR}`);
    console.log();
    startSocket();
  } else {
    const BRIDGE_BIND = process.env.BRIDGE_BIND || '127.0.0.1';
    app.listen(PORT, BRIDGE_BIND, () => {
      console.log(`🌉 WhatsApp bridge listening on port ${PORT} (mode: ${WHATSAPP_MODE})`);
      console.log(`📁 Session stored in: ${SESSION_DIR}`);
      if (ALLOWED_USERS.size > 0) {
        console.log(`🔒 Allowed users: ${Array.from(ALLOWED_USERS).join(', ')}`);
      } else if (WHATSAPP_MODE === 'self-chat') {
        console.log(`🔒 Self-chat mode — only your own messages to yourself are processed.`);
      } else {
        console.log(`🔒 No WHATSAPP_ALLOWED_USERS set — incoming messages are rejected.`);
        console.log(`   Set WHATSAPP_ALLOWED_USERS=<phone> to authorize specific users,`);
        console.log(`   or WHATSAPP_ALLOWED_USERS=* for an explicit open bot.`);
      }
      if (TRUSTED_GROUPS.size > 0) {
        console.log(
          `🔓 Trusted groups (all members allowed): ${Array.from(TRUSTED_GROUPS).join(', ')}`,
        );
      }
      console.log();
      startSocket();
    });
  }
} // end !RELAY_MODE
