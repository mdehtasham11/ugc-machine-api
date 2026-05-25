const fs = require("fs");
const path = require("path");

const api = (process.env.UGC_API_URL || "").trim().replace(/\/$/, "");
if (!api) {
  console.warn(
    "WARNING: UGC_API_URL is not set. Set it in Vercel → Settings → Environment Variables to your Render URL."
  );
}
const out = `window.UGC_API_URL = ${JSON.stringify(api)};\n`;
fs.writeFileSync(path.join(__dirname, "config.js"), out);
console.log("Wrote config.js →", api || "(empty, same-origin fallback)");
