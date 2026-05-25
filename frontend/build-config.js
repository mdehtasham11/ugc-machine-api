const fs = require("fs");
const path = require("path");

const DEFAULT_API_URL = "https://ugc-machine-api.onrender.com";
const LEGACY_API_URL = "https://ugc-machine-api-i4h2.onrender.com";
const envApi = (process.env.UGC_API_URL || "").trim().replace(/\/$/, "");
const api = !envApi || envApi === LEGACY_API_URL ? DEFAULT_API_URL : envApi;
if (!api) {
  console.warn(
    "WARNING: UGC_API_URL is not set. Set it in Vercel → Settings → Environment Variables to your Render URL."
  );
}
const out = `window.UGC_API_URL = ${JSON.stringify(api)};\n`;
fs.writeFileSync(path.join(__dirname, "config.js"), out);
console.log("Wrote config.js →", api || "(empty, same-origin fallback)");
