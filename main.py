import os
import random
import datetime
import requests
import librosa
from PIL import Image
from io import BytesIO
from duckduckgo_search import DDGS
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

GITHUB_USER = "nishantha31-eng"
REPO_NAME = "insta-auto-edits"

TOPICS = [
    {"query": "JDM sports car night aesthetic wallpaper", "caption": "Late night JDM vibes. 🏎️💨 #cars #jdm #carsofinstagram #reels"},
    {"query": "cricket stadium match action shot", "caption": "Pure cricket adrenaline. 🏏🔥 #cricket #cricketlovers #reels"},
    {"query": "football stadium night match players", "caption": "Under the stadium lights. ⚽✨ #football #soccer #footballreels"}
]

def download_images(query, count=6):
    os.makedirs("imgs", exist_ok=True)
    paths = []
    with DDGS() as ddgs:
        results = ddgs.images(query, max_results=30)
        for r in results:
            if len(paths) >= count:
                break
            try:
                resp = requests.get(r["image"], timeout=8)
                img = Image.open(BytesIO(resp.content)).convert("RGB")
                if img.width >= 720 and img.height >= 720:
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
                    path = f"imgs/img_{len(paths)}.jpg"
                    img.save(path, quality=95)
                    paths.append(path)
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
    audio_files = [f"audio/{f}" for f in os.listdir("audio") if f.endswith(".mp3")]
    chosen_audio = random.choice(audio_files)
    build_beat_synced_video(images, chosen_audio, "latest_reel.mp4")
    update_rss_feed(choice["caption"])
