import os
import requests
from supabase import create_client, Client

try:
    # 1. 環境変数の取得とSupabaseの初期化
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    youtube_api_key = os.environ.get("YOUTUBE_API_KEY")

    if not all([url, key, youtube_api_key]):
        raise ValueError("Error: 必要なAPIキー（環境変数）が設定されていません。")

    supabase: Client = create_client(url, key)

    # 2. 追跡対象の動画IDをSupabase（tracked_videos）から取得
    track_res = supabase.table('tracked_videos').select('video_id').execute()
    video_ids = [item['video_id'] for item in track_res.data]

    if not video_ids:
        print("追跡対象の動画がありません。")
        exit(0)

    # 3. YouTube API で最新の再生数などを一括取得
    stats_data = []
    ids_str = ",".join(video_ids)
    yt_url = f"https://www.googleapis.com/youtube/v3/videos?part=statistics&id={ids_str}&key={youtube_api_key}"
    
    yt_res = requests.get(yt_url)
    yt_res.raise_for_status()
    
    for item in yt_res.json().get("items", []):
        stats = item.get("statistics", {})
        stats_data.append({
            "video_id": item["id"],
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0))
        })

    # 4. 取得した最新データを Supabase (multi_video_stats) に保存
    if stats_data:
        supabase.table('multi_video_stats').insert(stats_data).execute()
        print(f"Success: {len(stats_data)} 件のデータを正常に更新しました！")

except Exception as e:
    print(f"Error updating data: {e}")
    exit(1)
