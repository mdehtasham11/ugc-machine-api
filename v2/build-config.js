const fs = require("fs");
const path = require("path");

const DEFAULT_API_URL = "https://ugc-machine-api-i4h2.onrender.com";
const api = (process.env.UGC_API_URL || DEFAULT_API_URL).trim().replace(/\/$/, "");
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
