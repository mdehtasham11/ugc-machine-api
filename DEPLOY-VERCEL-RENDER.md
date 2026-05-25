# Deploy: Vercel (frontend) + Render (backend)

The app is split because Vercel cannot run this backend (needs **FFmpeg**, **long jobs** 15–25+ minutes, disk for videos).

| Part | Host | Folder |
|------|------|--------|
| UI | **Vercel** | `v2/` |
| API | **Render** (Docker) | `ugc-machine/v2/` (`server.py` + `Dockerfile`) |

---

## 1. Deploy backend on Render

1. Push `ugc-machine` to GitHub (repo root can be `ugc-machine` or monorepo).
2. [Render Dashboard](https://dashboard.render.com) → **New** → **Web Service**.
3. Connect the repo.
4. Settings:
   - **Runtime:** Docker
   - **Root directory:** repo root
   - **Dockerfile path:** `v2/Dockerfile`
   - **Docker context:** `v2`
   - **Instance type:** at least **Starter** (not Free) — video jobs run 15–25+ minutes; Free spins down and may kill long work.
5. **Environment variables:**

   | Key | Value |
   |-----|--------|
   | `KIE_API_KEY` | Your key from https://kie.ai/api-key |
   | `KIE_BASE` | `https://api.kie.ai` |
   | `ALLOWED_ORIGIN` | Your Vercel URL, e.g. `https://ugc-machine.vercel.app` (no trailing slash) |

6. **Disk (recommended):** Add a persistent disk mounted at `/app/outputs` (1 GB+), or use the disk block in `render.yaml`.
7. Deploy. Copy your service URL, e.g. `https://ugc-machine-api.onrender.com`.
8. Test: open `https://YOUR-RENDER-URL.onrender.com/config-status` → should show `"configured": true`.

Or use **Blueprint**: New → Blueprint → select repo with `render.yaml` in `ugc-machine/`.

---

## 2. Deploy frontend on Vercel

1. [Vercel Dashboard](https://vercel.com) → **Add New Project** → import the same repo.
2. Settings:
   - **Root directory:** `v2` if the GitHub repo root is this `ugc-machine` folder. Use `ugc-machine/v2` only if this folder lives inside a larger monorepo.
   - **Framework preset:** Other
   - Build command / output directory are read from `vercel.json` (`npm run build`, output `.`).
3. **Environment variable** (Production + Preview):

   | Key | Value |
   |-----|--------|
   | `UGC_API_URL` | `https://YOUR-RENDER-URL.onrender.com` (no trailing slash) |

4. Deploy. Open your Vercel URL and use the app.

5. Update Render `ALLOWED_ORIGIN` to match the final Vercel domain if you changed it.

---

## 3. Local development

**Backend:**
```powershell
cd ugc-machine
# config.json or env KIE_API_KEY
python server.py
```

**Frontend (optional, pointing at local API):**
```powershell
cd ugc-machine/frontend
$env:UGC_API_URL = "http://localhost:8745"
npm run build
npx serve .
```

Or just use http://localhost:8745 (v2 backend serves UI + API together). If opening `v2/index.html` through Live Server, make sure `v2/config.js` points to `http://localhost:8745`.

---

## Limitations (read this)

- **Not ideal for serverless** — the deployment guide warned against Vercel/Netlify for the API; only the static HTML belongs on Vercel.
- **Render Free** may sleep and **lose in-memory job state** on restart; use **Starter** for real use.
- **Outputs** on Render are on disk — without a persistent disk, files disappear on redeploy.
- **First request** to Render after sleep can take ~30s (cold start).

---

## Checklist

- [ ] Render Docker service live, `/config-status` → `configured: true`
- [ ] `KIE_API_KEY` set on Render only (never in Vercel)
- [ ] `UGC_API_URL` on Vercel points to Render
- [ ] `ALLOWED_ORIGIN` on Render matches Vercel domain
- [ ] Persistent disk on `/app/outputs` (optional but recommended)
