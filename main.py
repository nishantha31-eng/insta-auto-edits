import os
import glob
import random
import datetime
import requests
import numpy as np
import librosa
from PIL import Image
from scipy.io.wavfile import write as wav_write
from icrawler.builtin import BingImageCrawler
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

GITHUB_USER = "nishantha31-eng"
REPO_NAME = "insta-auto-edits"

TOPICS = [
    {"query": "JDM sports car night aesthetic", "caption": "Late night JDM vibes. 🏎️💨 #cars #jdm #carsofinstagram #reels"},
    {"query": "cricket stadium match action", "caption": "Pure cricket adrenaline. 🏏🔥 #cricket #cricketlovers #reels"},
    {"query": "football stadium night match players", "caption": "Under the stadium lights. ⚽✨ #football #soccer #footballreels"}
]

def generate_fallback_beat(output_audio="bg_track.wav", duration=16, bpm=130):
    sr = 44100
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    beat_interval = 60.0 / bpm
    beat_pos = (t % beat_interval) / beat_interval
    # Punchy sub-bass kick + hi-hat rhythm
    kick = np.sin(2 * np.pi * (55 + 90 * np.exp(-beat_pos * 18)) * t) * np.exp(-beat_pos * 8)
    hat = np.random.uniform(-0.15, 0.15, len(t)) * np.exp(-((t % (beat_interval / 2)) / (beat_interval / 2)) * 25)
    audio = np.clip(kick * 0.8 + hat, -1.0, 1.0)
    wav_write(output_audio, sr, (audio * 32767).astype(np.int16))
    return output_audio

def fetch_auto_audio(output_audio="bg_track.mp3"):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
    # Try Jamendo public royalty-free API (electronic / hiphop / phonk-style instrumentals)
    try:
        tag = random.choice(["electronic", "hiphop", "trap", "rock"])
        url = f"https://jamendo.com{tag}&vocalinstrumental=instrumental&audiodlformat=mp32"
        res = requests.get(url, headers=headers, timeout=15).json()
        tracks = [t for t in res.get("results", []) if t.get("audiodownload")]
        if tracks:
            chosen = random.choice(tracks)
            dl = requests.get(chosen["audiodownload"], headers=headers, timeout=25)
            if dl.status_code == 200 and len(dl.content) > 100_000:
                with open(output_audio, "wb") as f:
                    f.write(dl.content)
                return output_audio
    except Exception as e:
        print("Jamendo fetch skipped:", e)

    # Guaranteed fallback beat if external audio servers are busy
    return generate_fallback_beat("bg_track.wav")

def download_images(query, count=6):
    os.makedirs("raw_imgs", exist_ok=True)
    os.makedirs("imgs", exist_ok=True)
    crawler = BingImageCrawler(storage={"root_dir": "raw_imgs"})
    crawler.crawl(keyword=query, max_num=20)

    paths = []
    for raw_path in glob.glob("raw_imgs/*"):
        if len(paths) >= count:
            break
        try:
            img = Image.open(raw_path).convert("RGB")
            if img.width >= 500 and img.height >= 500:
                target_ratio = 1080 / 1920
                img_ratio = img.width / img.height
                if img_ratio > target_ratio:
                    new_w = int(img.height * target_ratio)
                    left = (img.width - new_w) // 2
                    img = img.crop((left, 0, left + new_w, img.height))
                else:
                    new_h = int(img.width / target_ratio)
                    top = (img.height - new_h) // 2
                    img = img.crop((0, top, img.width, top + new_h))
                img = img.resize((1080, 1920), Image.Resampling.LANCZOS)
                out_path = f"imgs/img_{len(paths)}.jpg"
                img.save(out_path, quality=95)
                paths.append(out_path)
        except Exception:
            continue
    return paths

def build_beat_synced_video(image_paths, audio_path, output_path="latest_reel.mp4"):
    y, sr = librosa.load(audio_path, duration=15)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)

    cuts = [0.0]
    for b in beat_times[3::4]:
        if b <= 14.0 and len(cuts) < len(image_paths):
            cuts.append(float(b))
    cuts.append(min(15.0, cuts[-1] + 2.5))

    clips = []
    for idx, img_path in enumerate(image_paths[:len(cuts)-1]):
        duration = max(0.8, cuts[idx+1] - cuts[idx])
        clip = (ImageClip(img_path)
                .set_duration(duration)
                .resize(lambda t: 1 + 0.06 * (t / duration))
                .set_position("center"))
        clips.append(clip)

    video = concatenate_videoclips(clips, method="compose")
    audio = AudioFileClip(audio_path).subclip(0, video.duration)
    video = video.set_audio(audio)
    video.write_videofile(output_path, fps=30, codec="libx264", audio_codec="aac")
    return output_path

def update_rss_feed(caption):
    now = datetime.datetime.now(datetime.timezone.utc)
    pub_date = now.strftime("%a, %d %b %Y %H:%M:%S +0000")
    unique_id = now.strftime("%Y%m%d%H%M%S")
    video_url = f"https://githubusercontent.com{GITHUB_USER}/{REPO_NAME}/main/latest_reel.mp4?v={unique_id}"

    rss_content = f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
  <title>Auto Sports and Car Edits</title>
  <link>https://github.com{GITHUB_USER}/{REPO_NAME}</link>
  <description>Automated daily edits</description>
  <item>
    <title>{caption}</title>
    <link>{video_url}</link>
    <guid>{unique_id}</guid>
    <pubDate>{pub_date}</pubDate>
    <description>{caption}</description>
    <enclosure url="{video_url}" type="video/mp4" />
  </item>
</channel>
</rss>
"""
    with open("feed.xml", "w", encoding="utf-8") as f:
        f.write(rss_content)

if __name__ == "__main__":
    choice = random.choice(TOPICS)
    images = download_images(choice["query"], count=6)
    chosen_audio = fetch_auto_audio("bg_track.mp3")
    build_beat_synced_video(images, chosen_audio, "latest_reel.mp4")
    update_rss_feed(choice["caption"])
