# UGC Machine

Avatar + performance prompt → seamless 30-second UGC video with motion and synced speech. Kling 3.0 primary, Seedance 2.0 secondary. Runs locally. One key (Kie).

## Setup (2 min)
1. Install Python 3 and ffmpeg (ffmpeg does the clip stitching + frame-chaining).
2. Terminal in this folder: `python3 server.py`
3. Open the created **config.json**, paste your `kie_api_key` (https://kie.ai/api-key).
4. `python3 server.py` again, open **http://localhost:8745**.

## Flow
1. **Build the avatar** — describe the person/wardrobe/background, generate the reference frame, redo cheaply until right.
2. **Performance** — write motion + spoken lines together (words in quotes after "says:"). Add a **voice anchor** (e.g. "warm late-30s woman, slight rasp") — it gets injected into every clip so the voice stays consistent across the whole video.
3. **Engine + go** — pick mode, engine, resolution, hit go.


## Product reference image + bring-your-own-avatar
In step 1 you have two avatar sources (toggle at the top):
- **Generate avatar** — describe it, optionally attach a **product reference image** (a photo of your real product). It's sent to the image model so your actual product appears in the scene instead of an invented lookalike. Nano Banana Pro is best for this.
- **Use my own image** — upload an avatar/scene you already have; it's used directly and skips generation. For talking-head, pick one facing the camera with a relaxed, slightly-open mouth.

Uploads go to Kie's temporary file host (free, auto-deleted after 3 days) so the generation API can fetch them by URL. Requires the Kie key to be set.

## How 30s gets built (stitching)
No model makes 30s in one shot, so the tool splits your performance at sentence boundaries into ~5s clips and joins them:
- **Seamless take** (default): each clip starts from the *last frame* of the previous one (frame-chaining), so the face/lighting/position carry over and it reads as one continuous video. Clips break on sentence ends so the voice seams land on natural pauses.
- **Multi-shot cuts**: each clip generated independently from the avatar frame, clean cuts. For concepts that change shot (talking head → product → reaction).

ffmpeg concatenates the clips into one MP4, auto-saved to **outputs/**.

## Cost (verified Kie rates, 30s, audio on)
- **Kling 3.0** — 1080p $0.135/s = **~$4.05** · 720p $0.10/s = **~$3.00**
- **Seedance 2.0** — 1080p $0.51/s = ~$15.30 · 720p $0.205/s = ~$6.15
Kling is ~3.8× cheaper at 1080p — it's your workhorse. Use Seedance only on a winning ad where you want its motion style. Test hooks at 720p, re-gen winners at 1080p.

## Audio
Audio is ON (the model speaks the lines, lip-synced). If clip-to-clip voice consistency ever bothers you on a final, the voice-anchor usually prevents it; for the rare miss, fix it manually in your ElevenLabs dashboard (voice changer over the exported file).

## Verified API wiring (zero guesses)
- Kling 3.0: `kling-3.0/video` on `/jobs/createTask`, `image_urls[0]`=first frame, `sound`, `mode` (pro=1080p/std=720p), `duration`.
- Seedance 2.0: `bytedance/seedance-2`, `first_frame_url`, `return_last_frame:true` (gives the chain frame directly), `generate_audio`, `resolution`.
- Both polled at `/jobs/recordInfo`. Images same endpoint.

## Swapping models
Edit `VIDEO_ENGINES` / `IMAGE_MODELS` at the top of server.py. Each video engine declares its api shape (`kling` or `seedance`) and model id.
