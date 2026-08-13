import streamlit as st
import sqlite3
import requests
import pandas as pd
from datetime import datetime
import re
import altair as alt

st.set_page_config(page_title="エンタメトレンド分析 SaaS", layout="wide")

st.title("ILLIT MV トレンド覇権ダッシュボード (MVP)")
st.markdown("**指標の定義:** `VPH` (直近の1時間あたり再生増加数) / `ENG` (エンゲージメント率 = 高評価÷再生数)")
st.divider()

API_KEY = "AIzaSyBaWeV6deabeQpxPqpElHZN0Nr0zUNKcEQ"

# 【進化ポイント】動画IDと「コンセプト」を紐付ける辞書型に変更
DEFAULT_CONCEPTS = {
    "Vk5-c_v4gMU": "イージーリスニング",
    "tbDGl7jEazA":,  # Cherish (My Love)
    "_Pk6xfju3l0":,  # I Got Your back(Feat. JISOO, MOMOKA of HANA)
    "bMhDJ0S0OBA":,  # It's me
    "9nEp9eeGaJk":,  # NOT ME
    "-01oDwXKSuE":,  # Sunday Morning
    "x_RYZsOfpKY":,  # NOT CUTE ANYMORE
    "HeqsjDF7Lw0":,  # 時よ止まれ（Toki Yo Tomare）
    "xRU1XXHIpIc":,  # bomb
    "wpokz1JhGl0":,  # oops!
    "GkG60kISnfc":,  # jellyous
    "negtrQu5mTA":,  # 빌려온 고양이 (Do the Dance)
    "qlgEadao-Sk":,  # Almond Chocolate
    "-nEGVrzPaiU":,  # Tick-Tack
    "UCmgGZbfjmk":,  # Lucky Girl Syndrome
}

# --- ここから追加：自動判別エンジン ---
CONCEPT_KEYWORDS = {
    "イージーリスニング": ["easy listening", "chill", "lo-fi", "アコースティック", "イージーリスニング", "magnetic"],
    "ティーンクラッシュ": ["teen crush", "ティーンクラッシュ", "rebel", "woke up"],
    "ガールクラッシュ": ["girl crush", "ガールクラッシュ", "badass", "hiphop", "blackpink", "aespa", "baddie", "xg"],
    "ハイティーン": ["high teen", "ハイティーン", "school", "prom", "cheerleader", "highschool"],
    "ダーク・ホラー": ["dark", "horror", "ダーク", "ホラー", "creepy", "mystery", "nightmare", "dreamcatcher"],
    "ストリート・ヒップホップ": ["street", "hiphop", "hip hop", "ストリート", "ヒップホップ", "rap", "swag"],
    "ファンタジー": ["fantasy", "ファンタジー", "magic", "fairytale", "fairy", "magical"],
    "清純・青春・キュート": ["pure", "cute", "innocent", "youth", "清純", "青春", "キュート", "かわいい", "kawaii"],
    "Y2K・レトロ": ["y2k", "retro", "レトロ", "nostalgia", "90s", "00s", "newjeans", "vintage"],
    "ディスコ・ファンク": ["disco", "funk", "ディスコ", "ファンク", "retro pop", "groove"],
    "SF・ファンタジー": ["sci-fi", "cyberpunk", "サイバーパンク", "宇宙", "alien", "space", "supernova"],
    "セクシー": ["sexy", "セクシー", "mature", "alluring", "sensual"],
    "エレガント・ロイヤル": ["elegant", "royal", "エレガント", "ロイヤル", "queen", "princess", "luxury", "ive"]
}

def auto_detect_concept(video_id):
    url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}&key={API_KEY}"
    response = requests.get(url).json()
    if "items" in response and len(response["items"]) > 0:
        snippet = response["items"][0]["snippet"]
        title_lower = snippet.get("title", "").lower()
        # タグリストを取得（小文字化）
        tags_lower = [tag.lower() for tag in snippet.get("tags", [])]
        
        # 1. コンセプトごとのスコア表を準備（最初は全員0点）
        scores = {concept: 0 for concept in CONCEPT_KEYWORDS.keys()}
        
        # 2. 判定ロジック
        for concept, keywords in CONCEPT_KEYWORDS.items():
            for kw in keywords:
                # タグの中に「完全一致」するキーワードがあれば高得点（+3）
                if kw in tags_lower:
                    scores[concept] += 3
                # タイトルの中にキーワードが含まれていれば中得点（+2）
                if kw in title_lower:
                    scores[concept] += 2
                    
        # 3. 最もスコアの高いコンセプトを算出
        best_concept = max(scores, key=scores.get)
        
        # 4. 1点以上獲得していればそのコンセプトを返し、0点なら「その他」にする
        if scores[best_concept] > 0:
            return best_concept
            
    return "その他"
# --- 追加ここまで ---

# 【進化ポイント】動画IDと「コンセプト」を紐付ける辞書型に変更
DEFAULT_CONCEPTS = {
    
}

if "video_concepts" not in st.session_state:
    st.session_state.video_concepts = DEFAULT_CONCEPTS.copy()

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

# 手動で選べるコンセプトのリスト
concept_options = [
    "イージーリスニング", "ティーンクラッシュ", "ガールクラッシュ", "ハイティーン", 
    "ダーク・ホラー", "ストリート・ヒップホップ", "ファンタジー", 
    "清純・青春・キュート", "Y2K・レトロ", "ディスコ・ファンク", 
    "SF・ファンタジー", "セクシー", "エレガント・ロイヤル", "その他"
]

# まず自動判定を試みるが、ユーザーがセレクトボックスで選べるようにする
default_concept = "その他"
if new_input and len(extract_video_id(new_input) or "") == 11:
    # URLが入力された瞬間、裏で自動判定のヒントを出す
    temp_vid = extract_video_id(new_input)
    default_concept = auto_detect_concept(temp_vid)

# デフォルトの選択肢を自動判定結果に合わせる（でもユーザーが変えられる）
try:
    default_index = concept_options.index(default_concept)
except ValueError:
    default_index = len(concept_options) - 1

selected_concept = st.sidebar.selectbox("🏷 コンセプトタグ (自動判定済・変更可)", concept_options, index=default_index)

if st.sidebar.button("分析対象に追加する"):
    vid = extract_video_id(new_input)
    if vid:
        if vid not in st.session_state.video_concepts:
            st.session_state.video_concepts[vid] = selected_concept
            st.sidebar.success(f"追加完了！ (分類: 【{selected_concept}】)")
        else:
            st.sidebar.warning("既に監視リストに存在します。")
    else:
        st.sidebar.error("有効なURLを入力してください。")

if st.sidebar.button("🗑️ リストをリセット"):
    st.session_state.video_concepts = DEFAULT_CONCEPTS.copy()
    st.sidebar.info("初期状態に戻しました。")

st.sidebar.divider()

# データ取得ロジック
if st.sidebar.button("🔄 最新トレンドデータを取得"):
    if st.session_state.video_concepts:
        ids_str = ",".join(st.session_state.video_concepts.keys())
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

# 分析・可視化ロジック
conn = sqlite3.connect('youtube_stats.db')
try:
    video_ids = list(st.session_state.video_concepts.keys())
    if video_ids:
        placeholders = ','.join(['?'] * len(video_ids))
        query = f"SELECT * FROM multi_video_stats WHERE video_id IN ({placeholders})"
        df = pd.read_sql_query(query, conn, params=video_ids)
        
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            stats_list = []
            
            for vid in video_ids:
                video_data = df[df['video_id'] == vid].sort_values('timestamp')
                if not video_data.empty:
                    latest = video_data.iloc[-1]
                    oldest = video_data.iloc[0]
                    
                    clean_title = latest['title'].replace("ILLIT (아일릿) ", "").replace(" '", "").replace("'", "")
                    views = latest['views']
                    likes = latest['likes']
                    concept = st.session_state.video_concepts[vid] # コンセプトを紐付け
                    
                    eng_rate = (likes / views * 100) if views > 0 else 0
                    time_diff_hours = (latest['timestamp'] - oldest['timestamp']).total_seconds() / 3600
                    
                    if time_diff_hours > 0.05:
                        vph = int((views - oldest['views']) / time_diff_hours)
                    else:
                        vph = 0
                        
                    stats_list.append({
                        "video_id": vid,
                        "タイトル": clean_title,
                        "コンセプト": concept,
                        "VPH (熱狂度)": vph,
                        "ENG率 (%)": round(eng_rate, 2),
                        "累計再生数": views
                    })
            
            stats_df = pd.DataFrame(stats_list)
            stats_df = stats_df.sort_values(by="VPH (熱狂度)", ascending=False).reset_index(drop=True)
            
            # 1. 各動画のランキング
            st.subheader("👑 現在の動画トレンド覇権 (トップ3)")
            cols = st.columns(3)
            for i in range(min(3, len(stats_df))):
                row = stats_df.iloc[i]
                cols[i].metric(
                    label=f"{i+1}位: {row['タイトル']}", 
                    value=f"🔥 {row['VPH (熱狂度)']:,} VPH",
                    delta=f"{row['コンセプト']} / ENG: {row['ENG率 (%)']}%"
                )
            
            st.divider()
            
            # 2. 【新機能】マクロトレンド（コンセプト別）分析
            st.subheader("🧩 マクロトレンド分析 (コンセプト別シェア)")
            
            # コンセプトごとにVPHを合計するロジック
            concept_df = stats_df.groupby('コンセプト')['VPH (熱狂度)'].sum().reset_index()
            concept_df = concept_df.sort_values(by='VPH (熱狂度)', ascending=False)
            
            col1, col2 = st.columns(2)
            with col1:
                st.write("**現在の市場を支配しているコンセプト**")
                st.dataframe(concept_df.style.format({"VPH (熱狂度)": "{:,}"}), use_container_width=True)
            with col2:
                if concept_df['VPH (熱狂度)'].sum() > 0:
                    # コンセプトのシェアを円グラフで直感的に表示
                    pie_chart = alt.Chart(concept_df).mark_arc().encode(
                        theta=alt.Theta(field="VPH (熱狂度)", type="quantitative"),
                        color=alt.Color(field="コンセプト", type="nominal"),
                        tooltip=["コンセプト", "VPH (熱狂度)"]
                    ).properties(height=300)
                    st.altair_chart(pie_chart, use_container_width=True)
                else:
                    st.info("※VPHデータが蓄積されるとここにパイチャートが表示されます。")
            
            st.divider()
            
            # 3. 詳細データ
            st.subheader("📊 詳細データ一覧")
            st.dataframe(
                stats_df.drop(columns=['video_id']).style.format({"累計再生数": "{:,}", "VPH (熱狂度)": "{:,}", "ENG率 (%)": "{:.2f}"}),
                use_container_width=True
            )
            
        else:
            st.info("👈 左側の「最新トレンドデータを取得」ボタンを押してデータを蓄積してください。")
except Exception as e:
    st.error(f"データ処理エラー: {e}")
finally:
    conn.close()
