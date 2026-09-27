import os
from datetime import datetime, timezone
from googleapiclient.discovery import build
from supabase import create_client, Client

# ==========================================
# 1. 環境変数・クライアント初期化
# ==========================================
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Supabase & YouTube クライアント作成
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

# 追跡対象の動画IDリスト（例）
TARGET_VIDEO_IDS = [
    "UCn...",  # 追跡したい動画IDを入れる
    "...",
]

def fetch_and_save_video_stats():
    if not TARGET_VIDEO_IDS:
        print("追跡対象の動画IDが設定されていません。")
        return

    # ==========================================
    # 2. YouTube APIからデータ取得 (snippet と statistics を同時取得)
    # ==========================================
    # ★ポイント: part に "snippet,statistics" を指定する！
    response = youtube.videos().list(
        part="snippet,statistics",
        id=",".join(TARGET_VIDEO_IDS)
    ).execute()

    records = []
    # 現在時刻（UTC）を取得
    current_timestamp = datetime.now(timezone.utc).isoformat()

    for item in response.get("items", []):
        video_id = item["id"]
        stats = item.get("statistics", {})
        snippet = item.get("snippet", {})

        # ★ポイント: snippet から公開日時 (publishedAt) を取得
        published_at = snippet.get("publishedAt")

        # 登録用データオブジェクトの作成
        record = {
            "video_id": video_id,
            "title": snippet.get("title", ""),  # 動画タイトルも一緒に保存しておくと便利
            "view_count": int(stats.get("viewCount", 0)),
            "like_count": int(stats.get("likeCount", 0)),
            "comment_count": int(stats.get("commentCount", 0)),
            "timestamp": current_timestamp,      # データ取得日時
            "published_at": published_at         # ★追加: 動画の公開日時
        }
        records.append(record)

    # ==========================================
    # 3. Supabaseにデータ挿入 (Insert)
    # ==========================================
    if records:
        data, count = supabase.table("multi_video_stats").insert(records).execute()
        print(f"[{current_timestamp}] {len(records)}件のデータをSupabaseに保存完了！")
    else:
        print("取得できた動画データがありませんでした。")

if __name__ == "__main__":
    fetch_and_save_video_stats()
