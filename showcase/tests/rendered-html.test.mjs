import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render(pathname = "/") {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request(`https://preview.example.test${pathname}`, {
      headers: {
        accept: "text/html",
        host: "preview.example.test",
        "x-forwarded-proto": "https",
      },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the NYC Taxi Intelligence case study", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>NYC Taxi Intelligence/);
  assert.match(html, /NYC taxi demand,/);
  assert.match(html, /100M\+/);
  assert.doesNotMatch(html, /codex-preview/);
});

test("publishes absolute social-preview metadata and a real PNG", async () => {
  const response = await render();
  const html = await response.text();
  const expectedImage = "https://preview.example.test/og.png";

  assert.match(html, new RegExp(`<meta property="og:image" content="${expectedImage}"`));
  assert.match(html, new RegExp(`<meta name="twitter:image" content="${expectedImage}"`));
  assert.match(html, /<meta property="og:url" content="https:\/\/preview\.example\.test"/);

  const image = await readFile(new URL("../public/og.png", import.meta.url));
  assert.deepEqual([...image.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
  assert.ok(image.byteLength > 100_000);
});

test("server-renders the recursive evaluation review surface", async () => {
  const response = await render("/review");
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /Recursive Evaluation Review/);
  assert.match(html, /先锁定评估方法/);
  assert.match(html, /96/);
  assert.match(html, /24×24/);
  assert.match(html, /NOT PERMITTED/);
  assert.match(html, /model_validation\.py/);
});
