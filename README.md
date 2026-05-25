# UGC Machine

UGC Machine is a small single-user web tool that turns an avatar prompt and a performance script into a short marketing video. It ships as one Python backend plus one static HTML frontend.

The backend keeps the Kie.ai API key private, calls the Kie.ai image/video APIs, stores generated files in `outputs/`, and uses FFmpeg to stitch clips.

## Local Setup

1. Install Python 3.10+ and FFmpeg.
2. From this folder, run `python server.py`.
3. Edit the generated `config.json` and paste your Kie.ai API key.
4. Run `python server.py` again and open `http://localhost:8745`.

On Windows, you can also run:

```powershell
.\start-local.ps1
```

## Deployment Checklist

The PDF guide recommends a small Ubuntu 24.04 VPS rather than serverless hosting, because video jobs can run for many minutes and FFmpeg must be installed.

1. Create a VPS with Ubuntu 24.04.
2. Install dependencies:

```bash
sudo apt update
sudo apt install -y python3 ffmpeg
```

3. Upload this `ugc-machine/` folder to the server.
4. Copy `config.json.example` to `config.json` and add the real Kie.ai API key.
5. Test the app:

```bash
cd ugc-machine
python3 server.py
```

The app listens on port `8745`.

## Production Service

Deployment templates are in `deploy/`:

- `ugc.service` runs the app under systemd.
- `nginx-ugc.conf` reverse-proxies a domain to `127.0.0.1:8745` with long request timeouts.
- `cleanup-outputs.cron` removes old generated outputs.
- `server-setup.sh` installs dependencies and wires systemd/Nginx on Ubuntu.

Example setup after upload:

```bash
cd /home/user/ugc-machine
bash deploy/server-setup.sh /home/user/ugc-machine ugc.yourdomain.com user
```

After DNS points to the server, enable HTTPS:

```bash
sudo certbot --nginx -d ugc.yourdomain.com
```

## Security

`config.json` is ignored by git. Never put the API key in frontend code or commit it.

The app has no login. Before exposing it publicly, add HTTP Basic Auth in Nginx:

```bash
sudo htpasswd -c /etc/nginx/.htpasswd yourusername
```

Then uncomment the `auth_basic` lines in `/etc/nginx/sites-available/ugc` and reload Nginx.

## Operations

Check the service:

```bash
sudo systemctl status ugc
journalctl -u ugc -f
```

Restart after changes:

```bash
sudo systemctl restart ugc
```

Install the cleanup cron from `deploy/cleanup-outputs.cron` to remove files older than 14 days.
