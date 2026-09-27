import os
import requests
from datetime import datetime, timezone
from supabase import create_client, Client

# --- 1. 環境変数の取得 ---
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def fetch_and_save():
    # ==========================================
    # 2. Supabaseから「追跡対象の動画ID」を全取得する
    # ==========================================
    get_url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/tracked_videos?select=video_id"
    res_tracked = requests.get(get_url, headers=headers)
    
    if res_tracked.status_code != 200 or not res_tracked.json():
        print("追跡対象の動画IDがSupabaseに1件も登録されていません。Streamlit側でURLを入力してください。")
        return

    # IDリストを抽出
    target_video_ids = [item["video_id"] for item in res_tracked.json()]
    print(f"🎯 追跡対象の動画 ({len(target_video_ids)}件): {target_video_ids}")

    # ==========================================
    # 3. YouTube APIでデータ一括取得
    # ==========================================
    ids_str = ",".join(target_video_ids)
    yt_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&id={ids_str}&key={YOUTUBE_API_KEY}"
    
    res = requests.get(yt_url).json()
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
            "timestamp": current_time,
            "published_at": snippet.get("publishedAt") # 公開日時
        })

    # ==========================================
    # 4. Supabaseに蓄積保存
    # ==========================================
    if records:
        supabase.table("multi_video_stats").insert(records).execute()
        print(f"[{current_time}] {len(records)}件のデータを蓄積完了！")

if __name__ == "__main__":
    fetch_and_save()
