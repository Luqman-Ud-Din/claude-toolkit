const pino = require('pino');

// JSON to stdout. No redact paths are configured.
module.exports = pino({ level: process.env.LOG_LEVEL || 'info' });
