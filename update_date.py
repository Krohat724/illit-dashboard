import os
import requests
from datetime import datetime

API_KEY = os.environ.get("YOUTUBE_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def main():
    # 1. 登録されている動画IDをSupabaseから取得
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/video_concepts?select=video_id,title"
    res = requests.get(url, headers=headers)
    if res.status_code != 200 or not res.json():
        print("No videos found.")
        return

    video_ids = [row['video_id'] for row in res.json()]
    ids_str = ",".join(video_ids)

    # 2. YouTube APIで最新の統計を取得
    yt_url = f"https://www.googleapis.com/youtube/v3/videos?part=statistics,snippet&id={ids_str}&key={API_KEY}"
    yt_res = requests.get(yt_url).json()

    if "items" not in yt_res:
        print("YouTube API error.")
        return

    # 3. Supabaseに保存
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
        requests.post(f"{SUPABASE_URL.rstrip('/')}/rest/v1/multi_video_stats", headers=headers, json=payload)
    
    print(f"Updated {len(yt_res['items'])} videos at {now}")

if __name__ == "__main__":
    main()
