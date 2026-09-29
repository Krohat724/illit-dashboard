import os
import requests

# 1. GitHub Secrets から設定を読み込む
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not all([YOUTUBE_API_KEY, SUPABASE_URL, SUPABASE_KEY]):
    print("Error: 必要なAPIキーが設定されていません。")
    exit(1)

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# 2. Supabase の tracked_videos から追跡中の動画ID一覧を取得
track_url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/tracked_videos?select=video_id"
try:
    res = requests.get(track_url, headers=headers)
    res.raise_for_status()
    # 取得したデータから動画IDのリストを作る
    video_ids = [item['video_id'] for item in res.json()]
except Exception as e:
    print(f"Error: 動画IDの取得に失敗しました - {e}")
    exit(1)

if not video_ids:
    print("追跡対象の動画がありません。")
    exit(0)

# 3. YouTube API で最新の再生数などを一括取得
stats_data = []
ids_str = ",".join(video_ids)
yt_url = f"https://www.googleapis.com/youtube/v3/videos?part=statistics&id={ids_str}&key={YOUTUBE_API_KEY}"

try:
    res = requests.get(yt_url)
    res.raise_for_status()
    for item in res.json().get("items", []):
        stats = item.get("statistics", {})
        stats_data.append({
            "video_id": item["id"],
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0))
        })
except Exception as e:
    print(f"Error: YouTube APIの取得に失敗しました - {e}")
    exit(1)

# 4. 取得した最新データを Supabase (multi_video_stats) に保存
if stats_data:
    insert_url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/multi_video_stats"
    try:
        res = requests.post(insert_url, headers=headers, json=stats_data)
        res.raise_for_status()
        print(f"Success: {len(stats_data)} 件のデータを正常に保存しました！")
    except Exception as e:
        print(f"Error: データの保存に失敗しました - {e}")
        exit(1)
