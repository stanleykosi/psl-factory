// F-27 fidelity helper (copied from F-18) (test only): serves the frozen pages from <root>/frozen on 4803 and passes every
// other path (/_next CSS, fonts, images) through to the app on 4801, so the frozen pages load their own styles and
// fonts from the same origin. Usage: node serve-frozen.mjs [root] [port] [app origin]
import { createReadStream, existsSync, statSync } from 'node:fs';
import { createServer, request } from 'node:http';
import { dirname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = process.argv[2] ?? dirname(fileURLToPath(import.meta.url));
const port = Number(process.argv[3] ?? 4803);
const app = new URL(process.argv[4] ?? 'http://localhost:4801');

createServer((req, res) => {
  const path = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  if (path.startsWith('/frozen/')) {
    const file = normalize(join(root, path));
    if (!file.startsWith(join(root, 'frozen')) || !existsSync(file) || !statSync(file).isFile()) {
      res.writeHead(404).end();
      return;
    }
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    createReadStream(file).pipe(res);
    return;
  }
  const upstream = request({ host: app.hostname, port: app.port, path: req.url, method: req.method, headers: { ...req.headers, host: app.host } }, (up) => {
    res.writeHead(up.statusCode ?? 502, up.headers);
    up.pipe(res);
  });
  upstream.on('error', () => res.writeHead(502).end());
  req.pipe(upstream);
}).listen(port, () => console.log(`frozen pages on http://localhost:${port}/frozen/`));
