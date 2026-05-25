const fs = require("fs");
const path = require("path");

const api = (process.env.UGC_API_URL || "").trim().replace(/\/$/, "");
if (!api) {
  console.warn(
    "WARNING: UGC_API_URL is not set. Set it in Vercel to your Render backend URL."
  );
}

fs.writeFileSync(
  path.join(__dirname, "config.js"),
  `window.UGC_API_URL = ${JSON.stringify(api)};\n`
);
console.log("Wrote config.js ->", api || "(same-origin fallback)");
