import streamlit as st
import sqlite3
import requests
import pandas as pd
from datetime import datetime
import re

st.set_page_config(page_title="ILLIT MV Analysis Dashboard", layout="wide")

st.title("ILLIT MV リアルタイム分析ダッシュボード")
st.write("YouTubeのURLや動画IDを入力して、リアルタイムで再生数を取得・比較できます。")

API_KEY = "AIzaSyBaWeV6deabeQpxPqpElHZN0Nr0zUNKcEQ"

# 初期表示用の動画IDリスト
DEFAULT_IDS = [
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

# セッション状態の初期化（画面上で動画リストを保持する仕組み）
if "video_ids" not in st.session_state:
    st.session_state.video_ids = DEFAULT_IDS.copy()

# URLまたは文字列から11桁の動画IDを抽出する関数
def extract_video_id(url_or_id):
    url_or_id = url_or_id.strip()
    if len(url_or_id) == 11 and not ("/" in url_or_id or "." in url_or_id):
        return url_or_id
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url_or_id)
    if match:
        return match.group(1)
    return None

# サイドバー設定
st.sidebar.header("⚙️ 動画の追加・管理")

# 1. 好きな動画のURL入力欄
new_input = st.sidebar.text_input("➕ YouTube動画URLまたはIDを入力", placeholder="https://www.youtube.com/watch?v=...")
if st.sidebar.button("動画を追加"):
    vid = extract_video_id(new_input)
    if vid:
        if vid not in st.session_state.video_ids:
            st.session_state.video_ids.append(vid)
            st.sidebar.success(f"動画を追加しました！ (ID: {vid})")
        else:
            st.sidebar.warning("既にリストに存在します。")
    else:
        st.sidebar.error("有効なYouTube URLまたは動画IDを入力してください。")

# リストのリセットボタン
if st.sidebar.button("🗑️ リストを初期状態に戻す"):
    st.session_state.video_ids = DEFAULT_IDS.copy()
    st.sidebar.info("初期状態に戻しました。")

st.sidebar.divider()

# 2. データ取得ボタン
if st.sidebar.button("🔄 最新データを取得する"):
    if st.session_state.video_ids:
        ids_str = ",".join(st.session_state.video_ids)
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

# データベースから表示
conn = sqlite3.connect('youtube_stats.db')
try:
    if st.session_state.video_ids:
        placeholders = ','.join(['?'] * len(st.session_state.video_ids))
        query = f'''
            SELECT * FROM multi_video_stats 
            WHERE video_id IN ({placeholders})
            AND id IN (SELECT MAX(id) FROM multi_video_stats GROUP BY video_id)
        '''
        df = pd.read_sql_query(query, conn, params=st.session_state.video_ids)
        conn.close()

        if not df.empty:
            st.subheader("📊 各楽曲の最新再生回数")
            
            # 3列ずつ折り返してカードを表示
            N_COLS = 3
            for i in range(0, len(df), N_COLS):
                batch = df.iloc[i:i + N_COLS]
                cols = st.columns(N_COLS)
                for idx, (_, row) in enumerate(batch.iterrows()):
                    clean_title = row['title'].replace("ILLIT (아일릿) ", "").replace(" '", "").replace("'", "")
                    cols[idx].metric(label=clean_title, value=f"{row['views']:,} 回")

            st.subheader("📈 再生回数比較グラフ")
            st.bar_chart(data=df, x='title', y='views')
        else:
            st.info("左側の「最新データを取得する」ボタンを押してください。")
except Exception as e:
    st.info("左側の「最新データを取得する」ボタンを押して初期データを取得してください。")
