%%writefile app.py
import streamlit as st
import sqlite3
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="K-POP Trend Dashboard", layout="wide")

st.title("🎵 K-POP MV リアルタイム分析ダッシュボード")
st.write("YouTube Data APIから取得した最新の再生数をリアルタイムで可視化します。")

API_KEY = "AIzaSyBaWeV6deabeQpxPqpElHZN0Nr0zUNKcEQ"
VIDEO_IDS = [
    "Vk5-c_v4gMU",  # ILLIT - Magnetic
    "tbDGl7jEazA",  # Cherish (My Love)
    "_Pk6xfju3l0"   # I Got Your back(Feat. JISOO, MOMOKA of HANA)
]

# サイドバーでデータ取得
if st.sidebar.button("🔄 最新データを取得する"):
    ids_str = ",".join(VIDEO_IDS)
    url = f"https://www.googleapis.com/youtube/v3/videos?part=statistics,snippet&id={ids_str}&key={API_KEY}"
    response = requests.get(url)
    data = response.json()

    if "items" in data:
        conn = sqlite3.connect('youtube_stats.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS multi_video_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT, video_id TEXT, title TEXT, views INTEGER, likes INTEGER, comments INTEGER
            )
        ''')
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        for item in data["items"]:
            cursor.execute('''
                INSERT INTO multi_video_stats (timestamp, video_id, title, views, likes, comments)
                VALUES (?, ?, ?, ?, ?, 0)
            ''', (now, item["id"], item["snippet"]["title"], int(item["statistics"].get('viewCount', 0)), int(item["statistics"].get('likeCount', 0))))

        conn.commit()
        conn.close()
        st.sidebar.success("最新データを取得しました！")

# データベースから「動画ごとの最新レコード」を確実に1件ずつ取得
conn = sqlite3.connect('youtube_stats.db')
try:
    query = '''
        SELECT * FROM multi_video_stats 
        WHERE id IN (SELECT MAX(id) FROM multi_video_stats GROUP BY video_id)
    '''
    df = pd.read_sql_query(query, conn)
    conn.close()

    if not df.empty:
        st.subheader("📊 各楽曲の最新再生回数")
        cols = st.columns(len(df))
        for idx, row in df.iterrows():
            with cols[idx]:
                # タイトル表示を綺麗に整形
                display_title = row['title'] if len(row['title']) <= 20 else row['title'][:20] + "..."
                st.metric(label=display_title, value=f"{row['views']:,} 回")

        st.subheader("📈 再生回数比較グラフ")
        st.bar_chart(data=df, x='title', y='views')
    else:
        st.info("左上の「最新データを取得する」ボタンを押してください。")
except Exception as e:
    st.info("左上の「最新データを取得する」ボタンを押して初期データを取得してください。")
