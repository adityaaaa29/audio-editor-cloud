
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, request, render_template_string, send_file, after_this_request
import yt_dlp

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

HTML = """
<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Audio Editor Cloud</title>
<style>
body {
    background: #101827;
    color: white;
    font-family: Arial;
    max-width: 650px;
    margin: 50px auto;
    padding: 15px;
}
main {
    background: #1c293b;
    padding: 28px;
    border-radius: 15px;
}
input {
    width: 100%;
    box-sizing: border-box;
    padding: 14px;
    margin: 15px 0;
    border-radius: 8px;
    border: 1px solid #52627a;
    background: #101827;
    color: white;
}
button {
    padding: 14px;
    width: 100%;
    background: #3478f6;
    color: white;
    border: 0;
    border-radius: 8px;
    font-weight: bold;
    cursor: pointer;
}
.info { color: #bdc9d9; line-height: 1.7; }
.error { color: #ff9999; }
</style>
</head>
<body>
<main>
<h1>Audio Editor Cloud</h1>
<p>Masukkan link YouTube untuk memproses audio.</p>
<form method="POST" action="/edit">
<input type="url" name="url"
placeholder="https://www.youtube.com/watch?v=..."
required>
<button type="submit">PROSES AUDIO</button>
</form>
<div class="info">
<b>Preset otomatis:</b><br>
Speed: 2.3x<br>
Pitch: +0 semitone (dipertahankan)<br>
Bass: +0 dB<br>
Reverb: pendekatan echo ringan<br>
Volume: 120%<br><br>
<b>Output:</b><br>
OGG Vorbis · 256 kbps · 44.1 kHz
</div>
{% if error %}
<p class="error">{{ error }}</p>
{% endif %}
</main>
</body>
</html>
"""

def valid_url(url):
    try:
        parsed = urlparse(url.strip())
        host = (parsed.hostname or "").lower()
        allowed = {
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "music.youtube.com",
            "youtu.be"
        }
        return parsed.scheme in ("http", "https") and host in allowed
    except Exception:
        return False

@app.route("/")
def home():
    return render_template_string(HTML, error=None)

@app.route("/edit", methods=["POST"])
def edit():
    url = request.form.get("url", "").strip()

    if not valid_url(url):
        return render_template_string(
            HTML, error="Link YouTube tidak valid."
        ), 400

    folder = Path(tempfile.mkdtemp(prefix="audio_"))
    source = folder / "source.%(ext)s"
    output = folder / "hasil_audio.ogg"

    try:
        options = {
            "format": "bestaudio/best",
            "outtmpl": str(source),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 30,
            "retries": 2
        }

        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([url])

        sources = list(folder.glob("source.*"))

        if not sources:
            raise RuntimeError("Audio sumber tidak ditemukan.")

        input_file = sources[0]

        audio_filter = (
            "bass=g=0,"
            "atempo=2.3,"
            "aecho=0.8:0.75:60:0.30,"
            "volume=1.0"
        )

        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-i", str(input_file),
            "-vn",
            "-af", audio_filter,
            "-ar", "44100",
            "-c:a", "libvorbis",
            "-b:a", "256k",
            str(output)
        ]

        subprocess.run(
            command,
            check=True,
            timeout=1200
        )

        if not output.exists() or output.stat().st_size == 0:
            raise RuntimeError("File hasil kosong.")

        @after_this_request
        def cleanup(response):
            shutil.rmtree(folder, ignore_errors=True)
            return response

        return send_file(
            output,
            as_attachment=True,
            download_name="hasil_audio_2x.ogg",
            mimetype="audio/ogg"
        )

    except Exception as exc:
        shutil.rmtree(folder, ignore_errors=True)
        message = str(exc)[:300]
        return render_template_string(
            HTML, error="Gagal: " + message
        ), 500

@app.route("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
