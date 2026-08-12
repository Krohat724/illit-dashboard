import streamlit as st
import sqlite3
import requests
import pandas as pd
from datetime import datetime
import re

st.set_page_config(page_title="エンタメトレンド分析 SaaS", layout="wide")

# UIヘッダー（プロ投資家・業界人向けにデザインを洗練）
st.title("ILLIT トレンド覇権ダッシュボード (MVP)")
st.markdown("**指標の定義:** `VPH` (直近の1時間あたり再生増加数) / `ENG` (エンゲージメント率 = 高評価÷再生数)")
st.divider()

API_KEY = "ここに自分のAPIキーを貼り付ける"

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
    "wpokz1JhGl0",  # oops!
    "GkG60kISnfc",  # jellyous
    "negtrQu5mTA",  # 빌려온 고양이 (Do the Dance)
    "qlgEadao-Sk",  # Almond Chocolate
    "-nEGVrzPaiU",  # Tick-Tack
    "UCmgGZbfjmk",  # Lucky Girl Syndrome
]

if "video_ids" not in st.session_state:
    st.session_state.video_ids = DEFAULT_IDS.copy()

def extract_video_id(url_or_id):
    url_or_id = url_or_id.strip()
    if len(url_or_id) == 11 and not ("/" in url_or_id or "." in url_or_id):
        return url_or_id
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url_or_id)
    if match:
        return match.group(1)
    return None

# サイドバー設定
st.sidebar.header("⚙️ トレンド監視対象の追加")
new_input = st.sidebar.text_input("➕ YouTube動画URL", placeholder="https://www.youtube.com/watch?v=...")
if st.sidebar.button("分析対象に追加"):
    vid = extract_video_id(new_input)
    if vid:
        if vid not in st.session_state.video_ids:
            st.session_state.video_ids.append(vid)
            st.sidebar.success(f"追加完了 (ID: {vid})")
        else:
            st.sidebar.warning("既に監視リストに存在します。")
    else:
        st.sidebar.error("有効なURLを入力してください。")

if st.sidebar.button("🗑️ リストをリセット"):
    st.session_state.video_ids = DEFAULT_IDS.copy()
    st.sidebar.info("初期状態に戻しました。")

st.sidebar.divider()

# データ取得ロジック
if st.sidebar.button("🔄 最新トレンドデータを取得"):
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
            st.sidebar.success("🔥 データを取得・蓄積しました！")

# 分析・可視化ロジック（ここがSaaSの心臓部）
conn = sqlite3.connect('youtube_stats.db')
try:
    if st.session_state.video_ids:
        placeholders = ','.join(['?'] * len(st.session_state.video_ids))
        query = f"SELECT * FROM multi_video_stats WHERE video_id IN ({placeholders})"
        df = pd.read_sql_query(query, conn, params=st.session_state.video_ids)
        
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            stats_list = []
            
            # 各動画ごとにVPHとエンゲージメント率を計算
            for vid in st.session_state.video_ids:
                video_data = df[df['video_id'] == vid].sort_values('timestamp')
                if not video_data.empty:
                    latest = video_data.iloc[-1]
                    oldest = video_data.iloc[0]
                    
                    clean_title = latest['title'].replace("ILLIT (아일릿) ", "").replace(" '", "").replace("'", "")
                    views = latest['views']
                    likes = latest['likes']
                    
                    # エンゲージメント率（%）
                    eng_rate = (likes / views * 100) if views > 0 else 0
                    
                    # VPH計算（時間差分）
                    time_diff_hours = (latest['timestamp'] - oldest['timestamp']).total_seconds() / 3600
                    if time_diff_hours > 0.05: # データ取得間隔が数分以上ある場合のみ計算
                        vph = int((views - oldest['views']) / time_diff_hours)
                    else:
                        vph = 0 # データが1件のみ、または短時間すぎる場合は0
                        
                    stats_list.append({
                        "タイトル": clean_title,
                        "VPH (熱狂度)": vph,
                        "ENG率 (%)": round(eng_rate, 2),
                        "累計再生数": views
                    })
            
            # データフレーム化してVPH（勢い）が高い順にソート
            stats_df = pd.DataFrame(stats_list)
            stats_df = stats_df.sort_values(by="VPH (熱狂度)", ascending=False).reset_index(drop=True)
            
            # ハイライト指標の表示（ランキング1位の覇権を強調）
            st.subheader("👑 現在のトレンド覇権 (トップ3)")
            cols = st.columns(3)
            for i in range(min(3, len(stats_df))):
                row = stats_df.iloc[i]
                cols[i].metric(
                    label=f"{i+1}位: {row['タイトル']}", 
                    value=f"🔥 {row['VPH (熱狂度)']:,} VPH",
                    delta=f"ENG率: {row['ENG率 (%)']}%"
                )
            
            st.divider()
            
            # 詳細データのテーブル表示
            st.subheader("📊 コンセプト別 分析データ一覧")
            st.dataframe(
                stats_df.style.format({"累計再生数": "{:,}", "VPH (熱狂度)": "{:,}", "ENG率 (%)": "{:.2f}"}),
                use_container_width=True
            )
            
            # VPH比較グラフ
            st.subheader("📈 リアルタイム勢い比較 (VPH)")
            st.bar_chart(data=stats_df, x='タイトル', y='VPH (熱狂度)')
            
        else:
            st.info("👈 左側の「最新トレンドデータを取得」ボタンを押してデータを蓄積してください。")
except Exception as e:
    st.error(f"データ処理エラー: {e}")
finally:
    conn.close()
