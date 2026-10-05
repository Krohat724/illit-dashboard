# YouTube APIで snippet と statistics を同時に取得
res = youtube.videos().list(
    part="snippet,statistics",
    id=",".join(video_ids)
).execute()

records = []
for item in res.get("items", []):
    video_id = item["id"]
    stats = item["statistics"]
    snippet = item["snippet"]
    
    # 公開日時の取得 (ISO 8601形式: 例 2024-03-25T09:00:00Z)
    published_at = snippet.get("publishedAt")
    
    records.append({
        "video_id": video_id,
        "view_count": int(stats.get("viewCount", 0)),
        "like_count": int(stats.get("likeCount", 0)),
        "comment_count": int(stats.get("commentCount", 0)),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "published_at": published_at  # ← 追加！
    })

# Supabaseにデータ挿入
supabase.table("multi_video_stats").insert(records).execute()
