/**
 * Custom server with cache headers for /data/*.json
 *
 * Usage: node server.mjs
 *
 * With Astro in middleware mode, this gives us full control
 * over HTTP headers for static assets.
 */
import http from 'node:http';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { createReadStream, existsSync, statSync } from 'node:fs';
import { handler } from './dist/server/entry.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PORT = process.env.PORT || 4321;
const HOST = process.env.HOST || 'localhost';

// Static file directory (Astro's client build output)
const CLIENT_DIR = join(__dirname, 'dist', 'client');

// MIME types for common static files
const MIME_TYPES = {
  '.html': 'text/html',
  '.css': 'text/css',
  '.js': 'text/javascript',
  '.mjs': 'text/javascript',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.webp': 'image/webp',
};

// Cache control headers
const CACHE_HEADERS = {
  // /data/*.json - refreshed daily, cache 1h + 24h stale-while-revalidate
  '/data/': 'public, max-age=3600, stale-while-revalidate=86400',
  // /_astro/* - hashed assets, cache forever
  '/_astro/': 'public, max-age=31536000, immutable',
  // Default for other static files
  default: 'public, max-age=3600',
};

function getCacheControl(pathname) {
  for (const [prefix, value] of Object.entries(CACHE_HEADERS)) {
    if (prefix !== 'default' && pathname.startsWith(prefix)) {
      return value;
    }
  }
  return CACHE_HEADERS.default;
}

function getMimeType(filepath) {
  const ext = filepath.slice(filepath.lastIndexOf('.')).toLowerCase();
  return MIME_TYPES[ext] || 'application/octet-stream';
}

function serveStatic(req, res, pathname) {
  let filepath = join(CLIENT_DIR, pathname);

  // Security: prevent directory traversal
  if (!filepath.startsWith(CLIENT_DIR)) {
    res.statusCode = 403;
    res.end('Forbidden');
    return true;
  }

  // If path is a directory, try serving index.html
  if (existsSync(filepath) && statSync(filepath).isDirectory()) {
    filepath = join(filepath, 'index.html');
  }

  if (!existsSync(filepath)) {
    return false; // Let Astro handle it
  }

  const stat = statSync(filepath);
  if (stat.isDirectory()) {
    return false; // Still a directory, let Astro handle
  }

  // Set headers
  res.setHeader('Content-Type', getMimeType(filepath));
  res.setHeader('Content-Length', stat.size);
  res.setHeader('Cache-Control', getCacheControl(pathname));

  // Stream the file
  const stream = createReadStream(filepath);
  stream.pipe(res);
  return true;
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const pathname = url.pathname;

  // Try serving static files first
  if (serveStatic(req, res, pathname)) {
    return;
  }

  // Fall back to Astro SSR handler
  handler(req, res);
});

server.listen(PORT, HOST, () => {
  console.log(`Server running at http://${HOST}:${PORT}`);
  console.log(`Cache headers enabled for /data/*.json (1h + 24h stale-while-revalidate)`);
});
