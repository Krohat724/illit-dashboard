
import streamlit as st
import sqlite3
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="ILLIT Trend Dashboard", layout="wide")

st.title("ILLIT MV リアルタイム分析ダッシュボード")
st.write("YouTube Data APIから取得した最新の再生数をリアルタイムで可視化します。")

API_KEY = "AIzaSyBaWeV6deabeQpxPqpElHZN0Nr0zUNKcEQ"
VIDEO_IDS = [
    "Vk5-c_v4gMU",  # Magnetic
    "tbDGl7jEazA",  # Cherish (My Love)
    "_Pk6xfju3l0",  # I Got Your back(Feat. JISOO, MOMOKA of HANA)
    "bMhDJ0S0OBA",  # It's me
    "9nEp9eeGaJk",  # NOT ME
    "-01oDwXKSuE",  # Sunday Morning
    "x_RYZsOfpKY",  # NOT CUTE ANYMORE
    "HeqsjDF7Lw0",  # 時よ止まれ（Toki Yo Tomare）
    "xRU1XXHIpIc",  # bomb
    
]

# サイドバーでデータ取得
if st.sidebar.button(" 最新データを取得する"):
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
        st.subheader(" 各楽曲の最新再生回数")
        
    N_COLS = 3
    for i in range(0, len(df), N_COLS):
            batch = df.iloc[i:i + N_COLS]
            cols = st.columns(N_COLS)
            for idx, (_, row) in enumerate(batch.iterrows()):
                clean_title = row['title'].replace(" '", "").replace("'", "")
                cols[idx].metric(label=clean_title, value=f"{row['views']:,} 回")
                
        st.subheader("再生回数比較グラフ")
        st.bar_chart(data=df, x='title', y='views')
    else:
        st.info("左上の「最新データを取得する」ボタンを押してください。")
except Exception as e:
    st.info("左上の「最新データを取得する」ボタンを押して初期データを取得してください。")
