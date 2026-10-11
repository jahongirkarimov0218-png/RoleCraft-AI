// A fake OpenAI-compatible provider for the e2e run (loopback only, no network, no key).
// It behaves like a (very simple) model: every uncovered span of the prompt becomes a TaskNode quoting it.
// GET /__stats returns how many completion requests arrived; a prompt containing __LLM_DOWN__ makes it answer 503.
import { createServer } from "node:http";

const PORT = Number(process.env.PG_FAKE_LLM_PORT ?? 8002);
let completions = 0;
let lastAuth = null;

const server = createServer((req, res) => {
  if (req.method === "GET" && req.url === "/__stats") {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ completions, lastAuth }));
    return;
  }
  if (req.method === "POST" && req.url === "/v1/chat/completions") {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      completions += 1;
      lastAuth = req.headers.authorization ?? null;
      const body = JSON.parse(Buffer.concat(chunks).toString("utf-8"));
      const user = body.messages[1].content;
      if (user.includes("__LLM_DOWN__")) {
        res.writeHead(503, { "content-type": "application/json" });
        res.end(JSON.stringify({ error: { message: "model overloaded" } }));
        return;
      }
      const payload = JSON.parse(user);
      const nodes = payload.uncovered
        .filter((u) => u.text.trim().length > 0 && u.text.length <= 400)
        .map((u) => ({ type: "TaskNode", file: u.file, quote: u.text.trim(), description: "Proposed from uncovered text", confidence: 0.6 }));
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({ choices: [{ message: { role: "assistant", content: JSON.stringify({ nodes, edges: [] }) } }] }));
    });
    return;
  }
  res.writeHead(404);
  res.end();
});

server.listen(PORT, "127.0.0.1", () => console.log(`fake llm on ${PORT}`));
