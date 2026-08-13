import os
import requests
from datetime import datetime

API_KEY = os.environ.get("YOUTUBE_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

DEFAULT_IDS = ["Vk5-c_v4gMU", "a81S40mS_4A", "43MlyGCoQ7k"]

# Supabaseから現在の動画IDリストを取得
headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

res = requests.get(f"{SUPABASE_URL}/rest/v1/multi_video_stats?select=video_id", headers=headers)
if res.status_code == 200 and len(res.json()) > 0:
    video_ids = list(set([item["video_id"] for item in res.json()]))
else:
    video_ids = DEFAULT_IDS

# YouTube APIからデータ取得
ids_str = ",".join(video_ids)
yt_url = f"https://www.googleapis.com/youtube/v3/videos?part=statistics,snippet&id={ids_str}&key={API_KEY}"
yt_res = requests.get(yt_url).json()

if "items" in yt_res:
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for item in yt_res["items"]:
        payload = {
            "timestamp": now,
            "video_id": item["id"],
            "title": item["snippet"]["title"],
            "views": int(item["statistics"].get('viewCount', 0)),
            "likes": int(item["statistics"].get('likeCount', 0)),
            "comments": 0
        }
        # Supabaseへ直接データ送信 (INSERT)
        requests.post(f"{SUPABASE_URL}/rest/v1/multi_video_stats", headers=headers, json=payload)
    print(f"[{now}] Successfully updated {len(yt_res['items'])} videos to Supabase.")
else:
    print("Failed to fetch from YouTube.")
