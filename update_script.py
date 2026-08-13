import os
import sqlite3
import requests
from datetime import datetime

API_KEY = os.environ.get("YOUTUBE_API_KEY")
DEFAULT_IDS = ["Vk5-c_v4gMU", "a81S40mS_4A", "43MlyGCoQ7k"]

if not API_KEY:
    print("Error: YOUTUBE_API_KEY environment variable is missing.")
    exit(1)

conn = sqlite3.connect('youtube_stats.db')
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS multi_video_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT, video_id TEXT, title TEXT, views INTEGER, likes INTEGER, comments INTEGER
    )
''')

# DBにある全動画IDを動的取得
cursor.execute('SELECT DISTINCT video_id FROM multi_video_stats')
rows = cursor.fetchall()
video_ids = [r[0] for r in rows] if rows else DEFAULT_IDS

if video_ids:
    ids_str = ",".join(video_ids)
    url = f"https://www.googleapis.com/youtube/v3/videos?part=statistics,snippet&id={ids_str}&key={API_KEY}"
    response = requests.get(url)
    data = response.json()

    if "items" in data:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for item in data["items"]:
            cursor.execute('''
                INSERT INTO multi_video_stats (timestamp, video_id, title, views, likes, comments)
                VALUES (?, ?, ?, ?, ?, 0)
            ''', (now, item["id"], item["snippet"]["title"], int(item["statistics"].get('viewCount', 0)), int(item["statistics"].get('likeCount', 0))))
        conn.commit()
        print(f"[{now}] Successfully updated {len(data['items'])} videos.")
    else:
        print("Failed to fetch data from YouTube API:", data)

conn.close()
