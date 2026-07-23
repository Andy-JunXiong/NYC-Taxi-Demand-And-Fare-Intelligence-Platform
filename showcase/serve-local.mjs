import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const envPath = path.resolve(root, "..", ".env");
const env = Object.fromEntries(
  fs.readFileSync(envPath, "utf8")
    .split(/\r?\n/)
    .filter((line) => line && !line.trimStart().startsWith("#") && line.includes("="))
    .map((line) => {
      const split = line.indexOf("=");
      return [line.slice(0, split).trim(), line.slice(split + 1).trim()];
    }),
);

if (!env.GOOGLE_MAPS_API_KEY || !env.GOOGLE_MAP_ID) {
  throw new Error("GOOGLE_MAPS_API_KEY and GOOGLE_MAP_ID must be configured in the project .env");
}

const mime = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".png": "image/png",
  ".csv": "text/csv; charset=utf-8",
};

const server = http.createServer((req, res) => {
  if (req.url === "/runtime-config.js") {
    res.writeHead(200, { "Content-Type": mime[".js"], "Cache-Control": "no-store" });
    res.end(`window.NYC_TAXI_CONFIG=${JSON.stringify({
      googleMapsApiKey: env.GOOGLE_MAPS_API_KEY,
      googleMapId: env.GOOGLE_MAP_ID,
    })};`);
    return;
  }

  const requestPath = req.url === "/" ? "/nyc-taxi-intelligence.html" : decodeURIComponent(req.url.split("?")[0]);
  const absolute = path.resolve(root, `.${requestPath}`);
  if (!absolute.startsWith(`${root}${path.sep}`) || !fs.existsSync(absolute) || fs.statSync(absolute).isDirectory()) {
    res.writeHead(404);
    res.end("Not found");
    return;
  }
  res.writeHead(200, {
    "Content-Type": mime[path.extname(absolute).toLowerCase()] || "application/octet-stream",
    "Cache-Control": "no-store",
  });
  fs.createReadStream(absolute).pipe(res);
});

server.listen(3001, "127.0.0.1", () => {
  console.log("NYC Taxi Intelligence: http://localhost:3001");
});
