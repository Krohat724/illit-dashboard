import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import re
import altair as alt
import os

st.set_page_config(page_title="エンタメトレンド分析 SaaS", layout="wide")

st.title("ILLIT MV トレンド覇権ダッシュボード (MVP)")
st.markdown("**指標定義:** `VPH` (直近1時間の再生増加数) / `ENG` (エンゲージメント率 = 高評価÷再生数)")
st.divider()

# 環境変数の取得
API_KEY = st.secrets.get("YOUTUBE_API_KEY", os.environ.get("YOUTUBE_API_KEY"))
SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL"))
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", os.environ.get("SUPABASE_KEY"))

supabase_headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

DEFAULT_CONCEPTS = {
    "Vk5-c_v4gMU": "イージーリスニング",
}

CONCEPT_KEYWORDS = {
    "イージーリスニング": ["easy listening", "chill", "lo-fi", "アコースティック", "イージーリスニング", "magnetic"],
    "ティーンクラッシュ": ["teen crush", "ティーンクラッシュ", "rebel", "woke up"],
    "ガールクラッシュ": ["girl crush", "ガールクラッシュ", "badass", "hiphop", "blackpink", "aespa", "baddie", "xg"],
    "ハイティーン": ["high teen", "ハイティーン", "school", "prom", "cheerleader", "highschool"],
    "ダーク・ホラー": ["dark", "horror", "ダーク", "ホラー", "creepy", "mystery", "nightmare", "dreamcatcher"],
    "ストリート・ヒップホップ": ["street", "hiphop", "hip hop", "ストリート", "ヒップホップ", "rap", "swag"],
    "ファンタジー": ["fantasy", "ファンタジー", "magic", "fairytale", "fairy", "magical"],
    "清純・青春・キュート": ["pure", "cute", "innocent", "youth", "清純", "青春", "キュート", "kawaii"],
    "Y2K・レトロ": ["y2k", "retro", "レトロ", "nostalgia", "90s", "00s", "newjeans", "vintage"],
    "ディスコ・ファンク": ["disco", "funk", "ディスコ", "ファンク", "retro pop", "groove"],
    "SF・ファンタジー": ["sci-fi", "cyberpunk", "サイバーパンク", "宇宙", "alien", "space", "supernova"],
    "セクシー": ["sexy", "セクシー", "mature", "alluring", "sensual"],
    "エレガント・ロイヤル": ["elegant", "royal", "エレガント", "ロイヤル", "queen", "princess", "luxury", "ive"]
}

if "video_concepts" not in st.session_state:
    st.session_state.video_concepts = DEFAULT_CONCEPTS.copy()

def extract_video_id(url_or_id):
    url_or_id = url_or_id.strip()
    if len(url_or_id) == 11 and not ("/" in url_or_id or "." in url_or_id):
        return url_or_id
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url_or_id)
    return match.group(1) if match else None

def auto_detect_concept(video_id):
    try:
        url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}&key={API_KEY}"
        res = requests.get(url).json()
        if "items" in res and len(res["items"]) > 0:
            snippet = res["items"][0]["snippet"]
            title_lower = snippet.get("title", "").lower()
            tags_lower = [tag.lower() for tag in snippet.get("tags", [])]
            scores = {concept: 0 for concept in CONCEPT_KEYWORDS.keys()}
            for concept, keywords in CONCEPT_KEYWORDS.items():
                for kw in keywords:
                    if kw in tags_lower: scores[concept] += 3
                    if kw in title_lower: scores[concept] += 2
            best = max(scores, key=scores.get)
            if scores[best] > 0: return best
    except Exception:
        pass
    return "その他"

# サイドバー
st.sidebar.header("⚙️ 監視対象の追加")
new_input = st.sidebar.text_input("➕ YouTube動画URL", placeholder="https://www.youtube.com/watch?v=...")
if st.sidebar.button("⚡️ URLから追加"):
    vid = extract_video_id(new_input)
    if vid:
        if vid not in st.session_state.video_concepts:
            with st.sidebar.status("🤖 解析中..."):
                detected = auto_detect_concept(vid)
            st.session_state.video_concepts[vid] = detected
            st.sidebar.success(f"追加完了: 【{detected}】")
        else:
            st.sidebar.warning("既に存在します。")
    else:
        st.sidebar.error("有効なURLを入力してください。")

if st.sidebar.button("🗑️ リセット"):
    st.session_state.video_concepts = DEFAULT_CONCEPTS.copy()
    st.sidebar.info("初期状態に戻しました。")

st.sidebar.divider()

if st.sidebar.button("🔄 今すぐデータ取得"):
    if st.session_state.video_concepts:
        ids_str = ",".join(st.session_state.video_concepts.keys())
        url = f"https://www.googleapis.com/youtube/v3/videos?part=statistics,snippet&id={ids_str}&key={API_KEY}"
        res = requests.get(url).json()
        if "items" in res:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            success_count = 0
            for item in res["items"]:
                payload = {
                    "timestamp": now,
                    "video_id": item["id"],
                    "title": item["snippet"]["title"],
                    "views": int(item["statistics"].get('viewCount', 0)),
                    "likes": int(item["statistics"].get('likeCount', 0)),
                    "comments": 0
                }
                post_res = requests.post(f"{SUPABASE_URL}/rest/v1/multi_video_stats", headers=supabase_headers, json=payload)
                if post_res.status_code in [200, 201]:
                    success_count += 1
                else:
                    st.sidebar.error(f"保存失敗 ({post_res.status_code}): {post_res.text}")
            
            if success_count > 0:
                st.sidebar.success(f"Supabaseに{success_count}件のデータを保存しました！")
                st.rerun()

# データ可視化ロジック
try:
    video_ids = list(st.session_state.video_concepts.keys())
    if video_ids:
        # Supabaseからデータ取得
        res = requests.get(f"{SUPABASE_URL}/rest/v1/multi_video_stats?select=*", headers=supabase_headers)
        
        if res.status_code == 200 and len(res.json()) > 0:
            df = pd.DataFrame(res.json())
            df = df[df['video_id'].isin(video_ids)]
            
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                stats_list = []
                
                for vid in video_ids:
                    v_data = df[df['video_id'] == vid].sort_values('timestamp')
                    if not v_data.empty:
                        latest, oldest = v_data.iloc[-1], v_data.iloc[0]
                        clean_title = latest['title'].replace("ILLIT (아일릿) ", "").replace(" '", "").replace("'", "")
                        views, likes = latest['views'], latest['likes']
                        concept = st.session_state.video_concepts[vid]
                        
                        eng_rate = (likes / views * 100) if views > 0 else 0
                        time_diff = (latest['timestamp'] - oldest['timestamp']).total_seconds() / 3600
                        vph = int((views - oldest['views']) / time_diff) if time_diff > 0.05 else 0
                            
                        stats_list.append({
                            "video_id": vid, "タイトル": clean_title, "コンセプト": concept,
                            "VPH (熱狂度)": vph, "ENG率 (%)": round(eng_rate, 2), "累計再生数": views
                        })
                
                stats_df = pd.DataFrame(stats_list).sort_values(by="VPH (熱狂度)", ascending=False).reset_index(drop=True)
                
                st.subheader("👑 トレンド覇権 (トップ3)")
                cols = st.columns(3)
                for i in range(min(3, len(stats_df))):
                    row = stats_df.iloc[i]
                    cols[i].metric(label=f"{i+1}位: {row['タイトル']}", value=f"🔥 {row['VPH (熱狂度)']:,} VPH", delta=f"{row['コンセプト']} / ENG: {row['ENG率 (%)']}%")
                
                st.divider()
                
                st.subheader("🧩 コンセプト別シェア (マクロトレンド)")
                concept_df = stats_df.groupby('コンセプト')['VPH (熱狂度)'].sum().reset_index().sort_values(by='VPH (熱狂度)', ascending=False)
                
                c1, c2 = st.columns(2)
                with c1:
                    st.dataframe(concept_df.style.format({"VPH (熱狂度)": "{:,}"}), use_container_width=True)
                with c2:
                    if concept_df['VPH (熱狂度)'].sum() > 0:
                        pie = alt.Chart(concept_df).mark_arc().encode(
                            theta=alt.Theta(field="VPH (熱狂度)", type="quantitative"),
                            color=alt.Color(field="コンセプト", type="nominal"),
                            tooltip=["コンセプト", "VPH (熱狂度)"]
                        ).properties(height=300)
                        st.altair_chart(pie, use_container_width=True)
                    else:
                        st.info("※データ更新を複数回実行すると円グラフが表示されます。")
                
                st.divider()
                
                st.subheader("✏️ コンセプト修正 (手動チューニング)")
                all_options = list(CONCEPT_KEYWORDS.keys()) + ["その他"]
                for vid in video_ids:
                    curr_c = st.session_state.video_concepts[vid]
                    v_row = stats_df[stats_df['video_id'] == vid]
                    v_title = v_row['タイトル'].values[0] if not v_row.empty else vid
                    
                    idx = all_options.index(curr_c) if curr_c in all_options else len(all_options)-1
                    new_c = st.selectbox(f"🔗 「{v_title}」", all_options, index=idx, key=f"sel_{vid}")
                    if new_c != curr_c:
                        st.session_state.video_concepts[vid] = new_c
                        st.rerun()
                
                st.divider()
                st.subheader("📊 詳細データ一覧")
                st.dataframe(stats_df.drop(columns=['video_id']).style.format({"累計再生数": "{:,}", "VPH (熱狂度)": "{:,}", "ENG率 (%)": "{:.2f}"}), use_container_width=True)
            else:
                st.info("👈 左側の「今すぐデータ取得」を押してデータを初期生成してください。")
        else:
            st.info("👈 データベースが空です。左側の「今すぐデータ取得」を押してください。")
except Exception as e:
    st.error(f"エラー: {e}")
