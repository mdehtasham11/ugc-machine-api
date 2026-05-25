"""
UGC Machine - local backend.
Kling 3.0 (primary) + Seedance 2.0 (secondary). Builds 30s UGC by splitting your
performance prompt into clips, frame-chaining them for continuity, and stitching
with ffmpeg. Native audio (model speaks the lines). Auto-saves every result.

Run:  python3 server.py   ->   http://localhost:8745
"""

import os, json, time, uuid, threading, subprocess, re
import urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
OUTPUTS_DIR = os.path.join(HERE, "outputs")
STATIC_DIR  = os.path.join(HERE, "static")
PORT = int(os.environ.get("PORT", "8745"))

DEFAULT_CONFIG = {"kie_api_key": "PASTE_THE_REAL_KEY_HERE", "kie_base": "https://api.kie.ai"}
PLACEHOLDER_KEYS = {"", "PASTE_THE_REAL_KEY_HERE", "PASTE_YOUR_KIE_KEY_HERE"}

KIE_CREATE = "/api/v1/jobs/createTask"
KIE_RECORD = "/api/v1/jobs/recordInfo"

def _cors_origin():
    o = os.environ.get("ALLOWED_ORIGIN", "*").strip()
    return o if o else "*"

IMAGE_MODELS = {
    "nano-banana-pro": "nano-banana-pro",
    "gpt-image-2":     "gpt-image-2-text-to-image",
    "seedream-4.5":    "seedream-v4-5-text-to-image",
    "imagen4-ultra":   "google/imagen4-ultra",
}

# Both engines: native audio + first/last-frame chaining. Verified schemas.
#   kling -> model "kling-3.0/video", image_urls[0]=first frame, sound, mode, duration
#   seedance -> model "bytedance/seedance-2", first_frame_url, return_last_frame, generate_audio
VIDEO_ENGINES = {
    "kling-3.0":   {"api": "kling",    "model": "kling-3.0/video"},
    "seedance-2.0":{"api": "seedance", "model": "bytedance/seedance-2"},
}

# ---------------------------------------------------------------- config
def load_config():
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    cfg = dict(DEFAULT_CONFIG)
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w") as f: json.dump(DEFAULT_CONFIG, f, indent=2)
        print(f"\n>> Created {CONFIG_PATH}. Paste your Kie key (or set KIE_API_KEY env), then restart.\n")
    else:
        with open(CONFIG_PATH) as f: cfg.update(json.load(f))
    if os.environ.get("KIE_API_KEY", "").strip():
        cfg["kie_api_key"] = os.environ["KIE_API_KEY"].strip()
    if os.environ.get("KIE_BASE", "").strip():
        cfg["kie_base"] = os.environ["KIE_BASE"].strip()
    return cfg
CONFIG = load_config()

def is_configured():
    return CONFIG.get("kie_api_key", "").strip() not in PLACEHOLDER_KEYS

# ---------------------------------------------------------------- http
def _http(url, method="GET", headers=None, body=None, timeout=120):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode())
        except Exception: return e.code, {"error": str(e)}
    except Exception as e:
        return 0, {"error": str(e)}

def kie_headers():
    return {"Authorization": f"Bearer {CONFIG['kie_api_key']}", "Content-Type": "application/json"}

def kie_create(model, input_obj):
    status, resp = _http(CONFIG["kie_base"]+KIE_CREATE, "POST", kie_headers(),
                         {"model": model, "input": input_obj})
    if status == 200 and resp.get("code") == 200:
        return resp["data"]["taskId"], None
    return None, f"create failed ({status}): {resp.get('msg') or resp}"

def kie_poll(task_id, timeout=900):
    start, delay = time.time(), 3
    while time.time() - start < timeout:
        _, resp = _http(f"{CONFIG['kie_base']}{KIE_RECORD}?taskId={task_id}", headers=kie_headers())
        data = (resp or {}).get("data") or {}
        state = data.get("state")
        if state == "success":
            try:
                rj = json.loads(data.get("resultJson", "{}"))
                return rj.get("resultUrls", []), None
            except Exception as e:
                return None, f"result parse error: {e}"
        if state == "fail":
            return None, data.get("failMsg") or "generation failed"
        time.sleep(delay); delay = min(delay+1, 10)
    return None, "timeout"

def download(url, prefix):
    ext = os.path.splitext(url.split("?")[0])[1] or ".bin"
    fname = f"{prefix}_{int(time.time()*1000)}{ext}"
    try:
        urllib.request.urlretrieve(url, os.path.join(OUTPUTS_DIR, fname))
        return fname
    except Exception:
        return None

def extract_last_frame(video_path):
    """Pull final frame of a clip as a jpg, for Kling chaining (Kling has no return-frame)."""
    out = os.path.join(OUTPUTS_DIR, f"chainframe_{int(time.time()*1000)}.jpg")
    cmd = ["ffmpeg","-y","-sseof","-0.1","-i",video_path,"-vframes","1","-q:v","2",out]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return out if os.path.exists(out) else None
    except Exception:
        return None

def concat_clips(clip_paths, label="final"):
    """Stitch clips into one mp4. Re-encode for safe concat across clips."""
    # Filter out None and non-existent files
    clip_paths = [p for p in clip_paths if p and os.path.exists(p)]
    if not clip_paths: return None
    if len(clip_paths) == 1:
        out = os.path.join(OUTPUTS_DIR, f"ugc_{label}_{int(time.time())}.mp4")
        subprocess.run(["ffmpeg","-y","-i",clip_paths[0],"-c","copy",out],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return out if os.path.exists(out) else clip_paths[0]
    listfile = os.path.join(OUTPUTS_DIR, f"concat_{int(time.time())}.txt")
    norm = []
    for i, p in enumerate(clip_paths):
        n = os.path.join(OUTPUTS_DIR, f"norm_{int(time.time()*1000)}_{i}.mp4")
        subprocess.run(["ffmpeg","-y","-i",p,"-vf","scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2",
                        "-r","30","-c:v","libx264","-c:a","aac","-ar","44100",n],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        norm.append(n if os.path.exists(n) else p)
    with open(listfile,"w") as f:
        for n in norm: f.write(f"file '{n}'\n")
    out = os.path.join(OUTPUTS_DIR, f"ugc_{label}_{int(time.time())}.mp4")
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",listfile,"-c","copy",out],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out if os.path.exists(out) else None

# ---------------------------------------------------------------- segmenting
def split_segments(performance, voice_anchor, max_sentences=2):
    """Split the performance prompt into clip-sized chunks on sentence boundaries.
    Each segment gets the voice_anchor injected so the voice stays consistent."""
    # split into sentences but keep quoted dialogue intact
    parts = re.split(r'(?<=[.!?])\s+', performance.strip())
    parts = [p.strip() for p in parts if p.strip()]
    segs, cur = [], []
    for p in parts:
        cur.append(p)
        if len(cur) >= max_sentences:
            segs.append(" ".join(cur)); cur = []
    if cur: segs.append(" ".join(cur))
    if not segs: segs = [performance.strip()]
    if voice_anchor:
        segs = [f"{s}\n\nVoice: {voice_anchor}" for s in segs]
    return segs

# ---------------------------------------------------------------- job registry
JOBS, LOCK = {}, threading.Lock()
# caches the first clip per (inputs) so a Quick Check clip is reused by the full render
CLIP_CACHE = {}
def _clip_cache_key(engine, image_url, seg0, aspect, resolution, audio):
    import hashlib
    raw = f"{engine}|{image_url}|{seg0}|{aspect}|{resolution}|{audio}"
    return hashlib.md5(raw.encode()).hexdigest()
def set_job(jid, **kw):
    with LOCK: JOBS.setdefault(jid, {}); JOBS[jid].update(kw)
def get_job(jid):
    with LOCK: return dict(JOBS.get(jid, {}))

# ---------------------------------------------------------------- per-engine clip
def gen_clip(engine, prompt, first_frame_url, aspect, resolution, audio):
    """Generate ONE clip. Returns (video_url, error)."""
    eng = VIDEO_ENGINES[engine]
    if eng["api"] == "kling":
        mode = "pro" if resolution in ("1080p","1080") else "std"
        body = {
            "prompt": prompt,
            "image_urls": [first_frame_url] if first_frame_url else [],
            "sound": bool(audio),
            "duration": "5",
            "aspect_ratio": aspect,
            "mode": mode,
            "multi_shots": False,
        }
        tid, err = kie_create(eng["model"], body)
        if err: return None, err
        urls, err = kie_poll(tid)
        return (urls[0] if urls else None), err
    else:  # seedance
        body = {
            "prompt": prompt,
            "generate_audio": bool(audio),
            "resolution": resolution if resolution in ("480p","720p","1080p") else "720p",
            "aspect_ratio": aspect,
            "duration": 5,
            "return_last_frame": True,
        }
        if first_frame_url: body["first_frame_url"] = first_frame_url
        tid, err = kie_create(eng["model"], body)
        if err: return None, err
        urls, err = kie_poll(tid)
        return (urls[0] if urls else None), err

# ---------------------------------------------------------------- workers
def worker_image(jid, image_prompt, image_model_key):
    model = IMAGE_MODELS.get(image_model_key, IMAGE_MODELS["nano-banana-pro"])
    set_job(jid, status="running", step="image", message="generating reference frame...")
    image_input = {"prompt": image_prompt}
    if model == "nano-banana-pro":
        image_input.update({
            "image_input": [],
            "aspect_ratio": "9:16",
            "resolution": "1K",
            "output_format": "png",
        })
    tid, err = kie_create(model, image_input)
    if err: return set_job(jid, status="error", message=err)
    urls, err = kie_poll(tid)
    if err: return set_job(jid, status="error", message=f"image: {err}")
    local = download(urls[0], "frame") if urls else None
    set_job(jid, status="done", step="image", message="reference ready",
            data={"image_url": urls[0], "image_file": local})

def worker_video(jid, engine, image_url, performance, voice_anchor,
                 mode, aspect, resolution, audio, preview=False):
    """
    mode='chain'  : frame-chained, seamless single take. last frame -> next first frame.
    mode='cut'    : independent clips from the avatar image, hard cuts (multi-shot).
    preview=True  : generate ONLY the first clip (Quick Check) and stop. The clip is
                    cached so a following full render reuses it instead of paying again.
    """
    try:
        segs = split_segments(performance, voice_anchor)
        total = 1 if preview else len(segs)
        set_job(jid, status="running", step="video",
                message=f"0/{total} clips - starting...")
        clip_files = []
        prev_frame_url = image_url   # first clip starts from approved avatar
        cache_key = _clip_cache_key(engine, image_url, segs[0], aspect, resolution, audio)

        loop = segs[:1] if preview else segs
        for i, seg in enumerate(loop):
            label = "quick-check" if preview else f"clip {i+1}/{len(segs)}"
            set_job(jid, status="running", step="video",
                    message=f"{label} generating (synced speech)...")

            # reuse a cached first clip if we already made one for these exact inputs
            if i == 0 and cache_key in CLIP_CACHE and os.path.exists(CLIP_CACHE[cache_key]):
                fpath = CLIP_CACHE[cache_key]
                set_job(jid, status="running", step="video",
                        message=f"{label} reusing your quick-check clip...")
            else:
                start_frame = prev_frame_url if (mode == "chain" or i == 0) else image_url
                vurl, err = gen_clip(engine, seg, start_frame, aspect, resolution, audio)
                if err or not vurl:
                    return set_job(jid, status="error", message=f"{label}: {err or 'no url'}")
                fname = download(vurl, f"clip{i+1}")
                fpath = os.path.join(OUTPUTS_DIR, fname) if fname else None
                if not fpath or not os.path.exists(fpath):
                    return set_job(jid, status="error", message=f"{label}: download failed from {vurl}")
                if i == 0 and fpath:
                    CLIP_CACHE[cache_key] = fpath   # cache the first clip for reuse
            clip_files.append(fpath)

            # prep chaining frame for the next clip (skip in preview)
            if not preview and mode == "chain" and i < len(segs)-1 and fpath:
                set_job(jid, status="running", step="video",
                        message=f"clip {i+1}/{len(segs)} done - linking next...")
                lf = extract_last_frame(fpath)
                prev_frame_url = (upload_local(lf) or image_url) if lf else image_url

        if preview:
            # don't stitch - just hand back the single clip to eyeball
            pf = clip_files[0]
            pname = os.path.basename(pf) if pf else None
            return set_job(jid, status="done", step="preview", message="quick check ready",
                           data={"video_file": pname,
                                 "local_url": f"/outputs/{pname}" if pname else None,
                                 "preview": True})

        set_job(jid, status="running", step="stitch", message="stitching clips...")
        final = concat_clips(clip_files, label=engine.replace(".","_"))
        fname = os.path.basename(final) if final else None
        set_job(jid, status="done", step="video", message="video ready",
                data={"video_file": fname,
                      "local_url": f"/outputs/{fname}" if fname else None,
                      "clips": len(clip_files)})
    except Exception as e:
        set_job(jid, status="error", message=str(e))

def upload_local(path):
    """Upload a local file to Kie's file API so a chaining frame has a public URL.
    Falls back to None (engine then reuses the original avatar frame)."""
    try:
        # Kie file upload: multipart to /api/v1/file/upload (best-effort).
        import mimetypes
        boundary = "----ugc" + uuid.uuid4().hex
        fname = os.path.basename(path)
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        with open(path, "rb") as f: filedata = f.read()
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
                f"filename=\"{fname}\"\r\nContent-Type: {ctype}\r\n\r\n").encode() + filedata + \
               f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(CONFIG["kie_base"]+"/api/v1/file/upload",
                data=body, method="POST",
                headers={"Authorization": f"Bearer {CONFIG['kie_api_key']}",
                         "Content-Type": f"multipart/form-data; boundary={boundary}"})
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read().decode())
        return (resp.get("data") or {}).get("url") or resp.get("url")
    except Exception:
        return None

# ---------------------------------------------------------------- server
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, obj, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", _cors_origin())
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        if isinstance(obj,(dict,list)): self.wfile.write(json.dumps(obj).encode())
        elif isinstance(obj,bytes): self.wfile.write(obj)
        else: self.wfile.write(str(obj).encode())
    def _body(self):
        n = int(self.headers.get("Content-Length",0))
        return json.loads(self.rfile.read(n).decode()) if n else {}
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", _cors_origin())
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
    def do_GET(self):
        if self.path in ("/","/index.html"):
            with open(os.path.join(STATIC_DIR,"index.html"),"rb") as f:
                return self._send(200, f.read(), "text/html")
        if self.path == "/config.js":
            fp = os.path.join(STATIC_DIR, "config.js")
            if os.path.exists(fp):
                with open(fp, "rb") as f:
                    return self._send(200, f.read(), "application/javascript")
            return self._send(200, b"window.UGC_API_URL=window.UGC_API_URL||'';\n", "application/javascript")
        if self.path.startswith("/job/"):
            return self._send(200, get_job(self.path.split("/job/")[1]))
        if self.path.startswith("/outputs/"):
            fp = os.path.join(OUTPUTS_DIR, os.path.basename(self.path))
            if os.path.exists(fp):
                with open(fp,"rb") as f:
                    return self._send(200, f.read(), "video/mp4")
            return self._send(404, {"error":"not found"})
        if self.path == "/config-status":
            return self._send(200, {"configured": is_configured()})
        return self._send(404, {"error":"not found"})
    def do_POST(self):
        b = self._body()
        if self.path == "/gen-image":
            jid = uuid.uuid4().hex[:12]; set_job(jid, status="queued", step="image")
            threading.Thread(target=worker_image, args=(jid,
                b.get("image_prompt",""), b.get("image_model","nano-banana-pro")),
                daemon=True).start()
            return self._send(200, {"job_id": jid})
        if self.path == "/gen-video":
            jid = uuid.uuid4().hex[:12]; set_job(jid, status="queued", step="video")
            threading.Thread(target=worker_video, args=(jid,
                b.get("engine","kling-3.0"), b.get("image_url",""),
                b.get("performance",""), b.get("voice_anchor",""),
                b.get("mode","chain"), b.get("aspect_ratio","9:16"),
                b.get("resolution","1080p"), b.get("audio",True)),
                daemon=True).start()
            return self._send(200, {"job_id": jid})
        if self.path == "/quick-check":
            jid = uuid.uuid4().hex[:12]; set_job(jid, status="queued", step="preview")
            threading.Thread(target=worker_video, kwargs=dict(jid=jid,
                engine=b.get("engine","kling-3.0"), image_url=b.get("image_url",""),
                performance=b.get("performance",""), voice_anchor=b.get("voice_anchor",""),
                mode=b.get("mode","chain"), aspect=b.get("aspect_ratio","9:16"),
                resolution=b.get("resolution","1080p"), audio=b.get("audio",True),
                preview=True),
                daemon=True).start()
            return self._send(200, {"job_id": jid})
        return self._send(404, {"error":"not found"})

if __name__ == "__main__":
    print(f"\n  UGC Machine ->  http://localhost:{PORT}")
    print(f"  Outputs auto-saved to: {OUTPUTS_DIR}\n")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
