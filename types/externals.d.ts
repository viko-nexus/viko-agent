// Ambient declarations for the bridge's third-party deps. These packages ship
// their own types, but installing them (Baileys especially) is heavy and only
// needed at runtime — for type-checking we treat them as untyped. checkJs then
// verifies OUR logic (undefined refs, bad property access, null handling) without
// requiring the full dependency tree to be installed locally.
declare module '@whiskeysockets/baileys';
declare module 'express';
declare module '@hapi/boom';
declare module 'pino';
declare module 'qrcode-terminal';
