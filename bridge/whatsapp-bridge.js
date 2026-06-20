#!/usr/bin/env node
/**
 * whatsapp-bridge.js — WhatsApp bridge for viko-agent
 *
 * Standalone Node.js process that connects to WhatsApp via Baileys and
 * exposes the HTTP API that Hermes's gateway/platforms/whatsapp.py expects.
 *
 * Two modes (controlled by WHATSAPP_RELAY_MODE env var):
 *
 *   Admin mode (WHATSAPP_RELAY_MODE unset / false):
 *     - Holds the single WhatsApp session
 *     - Reads routing.json, dispatches group messages to per-port queues
 *     - Stamps [CTX project=slug caller=owner|member] on every routed message
 *     - Validates outbound relay tokens — each project container may only send
 *       to the exact group JID mapped to its relay_token
 *
 *   Project/Relay mode (WHATSAPP_RELAY_MODE=true):
 *     - No WhatsApp session — proxies all requests to the admin bridge
 *     - Filters polling to messages for this container's assigned port
 *
 * HTTP endpoints:
 *   GET  /messages       — Poll for new messages
 *   POST /send           — Send text { chatId, message }
 *   POST /edit           — Edit message { chatId, messageId, message }
 *   POST /typing         — Typing indicator { chatId }
 *   GET  /health         — Health / connectivity status
 *   GET  /relay/scope    — Admin: token → allowed JID introspection
 *
 * Usage:
 *   WHATSAPP_OWNER_NUMBER=628xxx node bridge/whatsapp-bridge.js
 *   WHATSAPP_RELAY_MODE=true WHATSAPP_RELAY_TARGET=http://viko-admin:3000 \
 *     HERMES_RELAY_TOKEN=xxx WHATSAPP_PORT_FILTER=3001 node bridge/whatsapp-bridge.js
 */

import { makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion } from '@whiskeysockets/baileys';
import express from 'express';
import { Boom } from '@hapi/boom';
import pino from 'pino';
import path from 'path';
import { mkdirSync, readFileSync, existsSync, watch } from 'fs';
import qrcode from 'qrcode-terminal';
import { parseAllowedUsers, matchesAllowedUser, normalizePhone } from './allowlist.js';

// ── Configuration ─────────────────────────────────────────────────────────────

const BRIDGE_PORT = parseInt(process.env.BRIDGE_PORT || '3000', 10);
const BRIDGE_BIND = process.env.BRIDGE_BIND || '0.0.0.0';

const SESSION_DIR = process.env.WHATSAPP_SESSION_DIR ||
  path.join(process.env.HOME || '/root', '.hermes', 'whatsapp', 'session');

const WHATSAPP_MODE = process.env.WHATSAPP_MODE || 'bot';
const ALLOWED_USERS = parseAllowedUsers(process.env.WHATSAPP_ALLOWED_USERS || '*');
const OWNER_WA = (process.env.WHATSAPP_OWNER_NUMBER || '').replace(/^\+/, '');

const RELAY_MODE = ['1', 'true', 'yes'].includes(
  (process.env.WHATSAPP_RELAY_MODE || '').toLowerCase()
);
const RELAY_TARGET = process.env.WHATSAPP_RELAY_TARGET || 'http://viko-admin:3000';
const PORT_FILTER = process.env.WHATSAPP_PORT_FILTER || '';
const RELAY_TOKEN = process.env.HERMES_RELAY_TOKEN || '';

const ROUTING_FILE = process.env.ROUTING_FILE || '/home/deploy/bridge/routing.json';

const REPLY_PREFIX = (process.env.WHATSAPP_REPLY_PREFIX ?? '').replace(/\\n/g, '\n');
const MAX_MSG_LEN = parseInt(process.env.WHATSAPP_MAX_MESSAGE_LENGTH || '4096', 10);
const CHUNK_DELAY_MS = parseInt(process.env.WHATSAPP_CHUNK_DELAY_MS || '300', 10);
const MAX_QUEUE_SIZE = 100;

// Injection patterns stripped from every inbound message before queuing.
// Blocks prompt-injection attempts that try to impersonate system markers.
const INJECTION_PATTERNS = [
  /\[CTX\s[^\]]*\]/gi,
  /\[SYSTEM[^\]]*\]/gi,
  /\[ADMIN[^\]]*\]/gi,
  /\[OWNER[^\]]*\]/gi,
  /\[RELAY[^\]]*\]/gi,
  /ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions?/gi,
  /forget\s+(?:your|all)\s+instructions?/gi,
  /you\s+are\s+now\s+(?:a\s+)?(?:different|new|another)/gi,
  /\[INST\][^\[]*\[\/INST\]/gi,
];

function sanitize(text) {
  let s = String(text || '');
  for (const p of INJECTION_PATTERNS) s = s.replace(p, '');
  return s.trim();
}

// ── Routing table (admin mode) ─────────────────────────────────────────────────

let _routing = {};     // { "jid@g.us": port_number }
let _tokenToJid = {};  // { "relay_token_hex": "jid@g.us" }
let _jidToSlug = {};   // { "jid@g.us": "project-slug" }

function loadRouting() {
  try {
    const raw = JSON.parse(readFileSync(ROUTING_FILE, 'utf8'));
    const routing = {}, tokenToJid = {}, jidToSlug = {};
    for (const [jid, val] of Object.entries(raw)) {
      if (val && typeof val === 'object') {
        if (val.port != null) routing[jid] = Number(val.port);
        if (val.relay_token) tokenToJid[val.relay_token] = jid;
        if (val.slug) jidToSlug[jid] = val.slug;
      } else if (typeof val === 'number') {
        routing[jid] = val; // legacy schema: { jid: port }
      }
    }
    _routing = routing; _tokenToJid = tokenToJid; _jidToSlug = jidToSlug;
    console.log(`[bridge] routing.json: ${Object.keys(_routing).length} routes`);
  } catch (e) {
    console.warn(`[bridge] Failed to load routing.json: ${e.message}`);
    _routing = {}; _tokenToJid = {}; _jidToSlug = {};
  }
}

if (!RELAY_MODE) {
  loadRouting();
  try {
    let reloadTimer;
    watch(path.dirname(ROUTING_FILE), { persistent: false }, (ev, fn) => {
      if (fn === path.basename(ROUTING_FILE)) {
        clearTimeout(reloadTimer);
        reloadTimer = setTimeout(loadRouting, 50);
      }
    });
  } catch {}
}

// ── Message queues (admin mode) ───────────────────────────────────────────────

const perPortQueues = {}; // { "3001": [message, ...] }
const globalQueue = [];   // unrouted messages → Admin Hermes

function enqueue(port, event) {
  const key = String(port);
  const q = (perPortQueues[key] = perPortQueues[key] || []);
  q.push(event);
  if (q.length > MAX_QUEUE_SIZE) q.shift();
}

function dequeuePort(port) {
  const key = String(port);
  const q = perPortQueues[key];
  if (!q || q.length === 0) return [];
  const msgs = q.splice(0);
  perPortQueues[key] = [];
  return msgs;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatOutgoing(text) {
  // Strip any CTX markers that leaked into outbound text
  let s = String(text || '')
    .replace(/\[(?:CTX|READ-ONLY MEMBER|Mentioned)\b[^\]]*\]/gi, '')
    .replace(/\bCTX\b[:.\s]*/gi, '')
    .replace(/^[\s:–—-]+/, '');
  if (s.length > 0) s = s.charAt(0).toUpperCase() + s.slice(1);
  if (WHATSAPP_MODE !== 'self-chat') return s;
  return REPLY_PREFIX ? `${REPLY_PREFIX.trimEnd()} ${s}` : s;
}

function splitMessage(text, max = MAX_MSG_LEN) {
  const s = String(text || '');
  if (!s || s.length <= max) return s ? [s] : [];
  const chunks = [];
  let rem = s;
  while (rem.length > max) {
    let at = rem.lastIndexOf('\n', max);
    if (at < max / 2) at = rem.lastIndexOf(' ', max);
    if (at < 1) at = max;
    chunks.push(rem.slice(0, at).trimEnd());
    rem = rem.slice(at).trimStart();
  }
  if (rem) chunks.push(rem);
  return chunks;
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function extractText(msg) {
  const m = msg.message || {};
  const inner =
    m.ephemeralMessage?.message ||
    m.viewOnceMessage?.message ||
    m.documentWithCaptionMessage?.message ||
    m;
  return (
    inner.conversation ||
    inner.extendedTextMessage?.text ||
    inner.imageMessage?.caption ||
    inner.videoMessage?.caption ||
    inner.documentMessage?.caption ||
    ''
  );
}

// ── Express app ───────────────────────────────────────────────────────────────

const app = express();
app.use(express.json({ limit: '10mb' }));

// ── RELAY MODE ────────────────────────────────────────────────────────────────

if (RELAY_MODE) {
  function relayHeaders() {
    return {
      'Content-Type': 'application/json',
      'Host': new URL(RELAY_TARGET).hostname,
      ...(RELAY_TOKEN ? { 'Authorization': `Bearer ${RELAY_TOKEN}` } : {}),
    };
  }

  async function fwd(res, upstream) {
    const text = await upstream.text();
    let body;
    try { body = text ? JSON.parse(text) : {}; }
    catch { body = { error: 'relay_parse_error', detail: text.slice(0, 300) }; }
    res.status(upstream.status).json(body);
  }

  app.get('/messages', async (req, res) => {
    try {
      const url = PORT_FILTER
        ? `${RELAY_TARGET}/messages?port=${PORT_FILTER}`
        : `${RELAY_TARGET}/messages`;
      const r = await fetch(url, { headers: relayHeaders() });
      res.json(await r.json());
    } catch { res.json([]); }
  });

  for (const ep of ['/send', '/edit', '/typing']) {
    app.post(ep, async (req, res) => {
      try {
        const r = await fetch(`${RELAY_TARGET}${ep}`, {
          method: 'POST',
          headers: relayHeaders(),
          body: JSON.stringify(req.body),
        });
        await fwd(res, r);
      } catch (e) {
        res.status(503).json({ error: 'relay_error', detail: e.message });
      }
    });
  }

  app.get('/health', async (req, res) => {
    try {
      const r = await fetch(`${RELAY_TARGET}/health`, { headers: relayHeaders() });
      const d = await r.json();
      res.json({ ...d, relay: true, port_filter: PORT_FILTER });
    } catch {
      res.json({ status: 'relay_disconnected', relay: true });
    }
  });

  app.listen(BRIDGE_PORT, '127.0.0.1', () => {
    console.log(`[bridge] Relay → ${RELAY_TARGET} (port_filter: ${PORT_FILTER || 'all'})`);
  });

} else {

// ── ADMIN MODE ────────────────────────────────────────────────────────────────

  // Outbound scope enforcement:
  //   - Loopback (127.0.0.1): Admin Hermes — unrestricted
  //   - Bearer token:         Project relay — scoped to token's JID only
  //   - No token, non-loopback: denied

  function bearerToken(req) {
    const m = (req.headers['authorization'] || '').match(/^Bearer\s+(.+)$/i);
    return m ? m[1].trim() : '';
  }
  function isLoopback(req) {
    const a = req.socket?.remoteAddress || '';
    return a === '127.0.0.1' || a === '::1' || a === '::ffff:127.0.0.1';
  }
  function scopeError(req, chatId) {
    const token = bearerToken(req);
    if (token) {
      const allowed = _tokenToJid[token];
      if (!allowed) return { code: 403, error: 'unknown_relay_token' };
      if (chatId && chatId !== allowed) {
        return { code: 403, error: 'cross_project_blocked', allowed_jid: allowed };
      }
      return null;
    }
    if (isLoopback(req)) return null;
    return { code: 403, error: 'relay_token_required' };
  }

  const SCOPED_PATHS = new Set(['/send', '/edit', '/typing']);
  app.use((req, res, next) => {
    if (req.method === 'POST' && SCOPED_PATHS.has(req.path)) {
      const err = scopeError(req, req.body?.chatId || '');
      if (err) {
        console.warn(`[bridge] scope-deny ${req.path} chatId=${req.body?.chatId || '?'} (${err.error})`);
        return res.status(err.code).json(err);
      }
    }
    next();
  });

  // Token introspection — project containers can self-verify their isolation scope
  app.get('/relay/scope', (req, res) => {
    const jid = _tokenToJid[bearerToken(req)];
    if (!jid) return res.status(403).json({ error: 'unknown_relay_token' });
    res.json({ port: _routing[jid], allowed_jids: [jid] });
  });

  // Message polling
  app.get('/messages', (req, res) => {
    const port = req.query.port ? String(req.query.port) : null;
    if (port) {
      res.json(dequeuePort(port));
    } else {
      const msgs = globalQueue.splice(0);
      res.json(msgs);
    }
  });

  // ── Baileys socket ──────────────────────────────────────────────────────────

  let sock = null;
  let connState = 'disconnected';
  const PAIR_ONLY = process.argv.includes('--pair-only');

  async function startSocket() {
    mkdirSync(SESSION_DIR, { recursive: true });
    const { state, saveCreds } = await useMultiFileAuthState(SESSION_DIR);
    const { version } = await fetchLatestBaileysVersion();

    sock = makeWASocket({
      version,
      auth: state,
      logger: pino({ level: 'warn' }),
      printQRInTerminal: false,
      browser: ['Viko Agent', 'Chrome', '120.0'],
      syncFullHistory: false,
      markOnlineOnConnect: false,
      getMessage: async () => ({ conversation: '' }),
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', ({ connection, lastDisconnect, qr }) => {
      if (qr) {
        console.log('\nScan this QR code with WhatsApp:\n');
        qrcode.generate(qr, { small: true });
        console.log('\nWaiting for scan...\n');
      }
      if (connection === 'close') {
        connState = 'disconnected';
        const code = new Boom(lastDisconnect?.error)?.output?.statusCode;
        if (code === DisconnectReason.loggedOut) {
          console.error('[bridge] Logged out. Delete session dir and restart to re-pair.');
          process.exit(1);
        }
        const delay = code === 515 ? 1000 : 3000;
        console.log(`[bridge] Disconnected (code ${code}). Reconnecting in ${delay}ms...`);
        setTimeout(startSocket, delay);
      } else if (connection === 'open') {
        connState = 'connected';
        console.log('[bridge] WhatsApp connected');
        if (PAIR_ONLY) {
          console.log('[bridge] Pairing complete. Credentials saved.');
          setTimeout(() => process.exit(0), 2000);
        }
      }
    });

    sock.ev.on('messages.upsert', async ({ messages, type }) => {
      if (type !== 'notify' && type !== 'append') return;

      for (const msg of messages) {
        if (!msg.message || msg.key.fromMe) continue;

        const chatId = msg.key.remoteJid;
        if (!chatId) continue;
        const isGroup = chatId.endsWith('@g.us');
        const senderJid = msg.key.participant || chatId;
        const phone = normalizePhone(senderJid);
        const isOwner = OWNER_WA && phone === OWNER_WA;

        // Non-group DMs: check allowlist
        if (!isGroup && !matchesAllowedUser(phone, ALLOWED_USERS)) continue;

        let body = extractText(msg);
        if (!body) continue;
        body = sanitize(body);
        if (!body) continue;

        const targetPort = isGroup ? _routing[chatId] : null;

        if (isGroup && targetPort) {
          // Registered group → stamp scope tag and route to project queue
          const slug = _jidToSlug[chatId] || 'unknown';
          const caller = isOwner ? 'owner' : 'member';
          body = `[CTX project=${slug} caller=${caller}]\n${body}`;

          enqueue(targetPort, {
            messageId: msg.key.id,
            chatId,
            senderId: senderJid,
            senderPhone: phone,
            body,
            isGroup: true,
            isOwner,
            timestamp: msg.messageTimestamp,
          });
        } else if (!isGroup || !targetPort) {
          // Unregistered group or DM — goes to Admin Hermes
          // For unregistered groups, only owner messages pass through
          if (isGroup && !isOwner) continue;

          // Stamp unregistered group messages so admin knows to offer onboard format
          const taggedBody = isGroup ? `[CTX unregistered_group=${chatId}]\n${body}` : body;
          globalQueue.push({
            messageId: msg.key.id,
            chatId,
            senderId: senderJid,
            senderPhone: phone,
            body: taggedBody,
            isGroup,
            isOwner,
            timestamp: msg.messageTimestamp,
          });
          if (globalQueue.length > MAX_QUEUE_SIZE) globalQueue.shift();
        }
      }
    });
  }

  // ── Outbound endpoints ──────────────────────────────────────────────────────

  app.post('/send', async (req, res) => {
    if (!sock || connState !== 'connected') {
      return res.status(503).json({ error: 'not_connected' });
    }
    const { chatId, message } = req.body;
    if (!chatId || !message) {
      return res.status(400).json({ error: 'chatId and message are required' });
    }
    try {
      const chunks = splitMessage(formatOutgoing(message));
      const ids = [];
      for (let i = 0; i < chunks.length; i++) {
        const sent = await sock.sendMessage(chatId, { text: chunks[i] });
        if (sent?.key?.id) ids.push(sent.key.id);
        if (i < chunks.length - 1) await sleep(CHUNK_DELAY_MS);
      }
      res.json({ success: true, messageId: ids[ids.length - 1], messageIds: ids });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  });

  app.post('/edit', async (req, res) => {
    if (!sock || connState !== 'connected') {
      return res.status(503).json({ error: 'not_connected' });
    }
    const { chatId, messageId, message } = req.body;
    if (!chatId || !messageId || !message) {
      return res.status(400).json({ error: 'chatId, messageId, and message are required' });
    }
    try {
      const text = splitMessage(formatOutgoing(message))[0] || '';
      await sock.sendMessage(chatId, {
        text,
        edit: { id: messageId, fromMe: true, remoteJid: chatId },
      });
      res.json({ success: true });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  });

  app.post('/typing', async (req, res) => {
    if (!sock || connState !== 'connected') return res.json({ ok: false });
    try {
      await sock.sendPresenceUpdate('composing', req.body.chatId);
      res.json({ ok: true });
    } catch {
      res.json({ ok: false });
    }
  });

  app.get('/health', (req, res) => {
    res.json({
      status: connState,
      routes: Object.keys(_routing).length,
      relay: false,
    });
  });

  app.listen(BRIDGE_PORT, BRIDGE_BIND, () => {
    console.log(`[bridge] Admin mode on ${BRIDGE_BIND}:${BRIDGE_PORT}`);
    startSocket().catch(e => {
      console.error('[bridge] Socket start failed:', e.message);
      process.exit(1);
    });
  });
}
