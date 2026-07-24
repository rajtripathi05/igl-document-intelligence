/* Netlify Function: /api/extract — AI extraction proxy for the Sales Order flow.
 *
 * The browser sends {filename, mime, data(base64)} for one customer PO
 * (PDF or image). This function forwards it to the configured AI provider
 * with the v2 Sales-Order prompts + schema and returns the extracted JSON.
 * The API key lives ONLY in Netlify environment variables:
 *
 *   AI_PROVIDER   openrouter (default) | gemini
 *   AI_API_KEY    the provider key                        (required)
 *   DEFAULT_MODEL openrouter: google/gemini-flash-latest  (default)
 *                 gemini:     gemini-flash-latest
 */
import { SYSTEM_PROMPT, EXTRACTION_PROMPT, SCHEMA } from "./prompts.mjs";

export const config = { path: "/api/extract" };

const MAX_BYTES = 4.5 * 1024 * 1024; // Netlify request body limit headroom

const instruction = () =>
  `${EXTRACTION_PROMPT}\n\nJSON SCHEMA (return exactly this structure):\n` +
  `${JSON.stringify(SCHEMA, null, 1)}\n\nReturn ONLY the JSON object.`;

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), {
    status, headers: { "content-type": "application/json" },
  });
}

function parseModelJson(text) {
  let t = String(text || "").trim();
  t = t.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "");
  const start = t.indexOf("{");
  const end = t.lastIndexOf("}");
  if (start >= 0 && end > start) t = t.slice(start, end + 1);
  return JSON.parse(t);
}

async function callOpenRouter(key, model, mime, data, filename) {
  const isPdf = mime === "application/pdf";
  const filePart = isPdf
    ? { type: "file", file: { filename: filename || "document.pdf",
        file_data: `data:${mime};base64,${data}` } }
    : { type: "image_url", image_url: { url: `data:${mime};base64,${data}` } };
  const body = {
    model: model || "google/gemini-flash-latest",
    messages: [
      { role: "system", content: SYSTEM_PROMPT },
      { role: "user", content: [{ type: "text", text: instruction() }, filePart] },
    ],
    response_format: { type: "json_object" },
    ...(isPdf ? { plugins: [{ id: "file-parser", pdf: { engine: "native" } }] } : {}),
  };
  const res = await fetch("https://openrouter.ai/api/v1/chat/completions", {
    method: "POST",
    headers: { authorization: `Bearer ${key}`, "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok)
    throw new Error(`OpenRouter ${res.status}: ${payload?.error?.message || JSON.stringify(payload).slice(0, 300)}`);
  const text = payload?.choices?.[0]?.message?.content;
  if (!text) throw new Error("OpenRouter returned an empty response.");
  return { text, usage: payload.usage || null };
}

async function callGemini(key, model, mime, data) {
  const m = model || "gemini-flash-latest";
  const res = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(m)}:generateContent`,
    {
      method: "POST",
      headers: { "x-goog-api-key": key, "content-type": "application/json" },
      body: JSON.stringify({
        systemInstruction: { parts: [{ text: SYSTEM_PROMPT }] },
        contents: [{ role: "user", parts: [
          { text: instruction() },
          { inlineData: { mimeType: mime, data } },
        ]}],
        generationConfig: { responseMimeType: "application/json" },
      }),
    },
  );
  const payload = await res.json().catch(() => ({}));
  if (!res.ok)
    throw new Error(`Gemini ${res.status}: ${payload?.error?.message || JSON.stringify(payload).slice(0, 300)}`);
  const text = payload?.candidates?.[0]?.content?.parts?.map((p) => p.text || "").join("");
  if (!text) throw new Error("Gemini returned an empty response.");
  return { text, usage: payload.usageMetadata || null };
}

export default async function handler(req) {
  if (req.method !== "POST") return jsonResponse(405, { ok: false, error: "POST only" });

  const key = process.env.AI_API_KEY;
  if (!key)
    return jsonResponse(500, { ok: false,
      error: "AI_API_KEY is not configured. Set it in Netlify → Site settings → Environment variables." });

  let body;
  try { body = await req.json(); }
  catch { return jsonResponse(400, { ok: false, error: "Invalid JSON body." }); }

  const { filename, mime, data } = body || {};
  if (!data || !mime)
    return jsonResponse(400, { ok: false, error: "Expected {filename, mime, data(base64)}." });
  if (data.length * 0.75 > MAX_BYTES)
    return jsonResponse(413, { ok: false, error: "File too large (max ~4.5 MB)." });

  const provider = (process.env.AI_PROVIDER || "openrouter").toLowerCase();
  const model = process.env.DEFAULT_MODEL || "";

  try {
    const call = provider === "gemini" ? callGemini : callOpenRouter;
    const { text, usage } = await call(key, model, mime, data, filename);
    let extracted;
    try { extracted = parseModelJson(text); }
    catch {
      return jsonResponse(502, { ok: false, error: "Model did not return valid JSON.", raw: String(text).slice(0, 2000) });
    }
    return jsonResponse(200, { ok: true, data: extracted, usage, provider, model: model || "(default)" });
  } catch (err) {
    return jsonResponse(502, { ok: false, error: String(err.message || err) });
  }
}
