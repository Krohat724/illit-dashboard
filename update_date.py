import os
import requests
from datetime import datetime, timezone
from supabase import create_client, Client

# --- 環境変数 ---
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 追跡対象の動画IDリスト（※必要に応じて追加・変更しろ）
TARGET_VIDEO_IDS = [
    "UCn...",  # 追跡したいYouTube動画ID
]

def fetch_and_save():
    if not TARGET_VIDEO_IDS:
        print("動画IDが設定されていません。")
        return

    ids_str = ",".join(TARGET_VIDEO_IDS)
    # ★ partに snippet,statistics を指定して公開日時(publishedAt)も同時に取得
    url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&id={ids_str}&key={YOUTUBE_API_KEY}"
    
    res = requests.get(url).json()
    items = res.get("items", [])
    
    current_time = datetime.now(timezone.utc).isoformat()
    records = []

    for item in items:
        v_id = item["id"]
        stats = item.get("statistics", {})
        snippet = item.get("snippet", {})
        
        records.append({
            "video_id": v_id,
            "title": snippet.get("title", ""),
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
            "timestamp": current_time,                  # データ取得日時
            "published_at": snippet.get("publishedAt") # ★動画の公開日時
        })

    if records:
        supabase.table("multi_video_stats").insert(records).execute()
        print(f"[{current_time}] {len(records)}件のデータを保存完了！")

if __name__ == "__main__":
    fetch_and_save()
