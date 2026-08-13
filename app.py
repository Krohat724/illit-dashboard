import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import re
import altair as alt
import os

st.set_page_config(page_title="エンタメトレンド分析 SaaS", layout="wide")

st.title("🔥 K-POP トレンド覇権ダッシュボード (MVP)")
st.markdown("**指標定義:** `VPH` (直近1時間の再生増加数) / `ENG` (エンゲージメント率 = 高評価÷再生数)")
st.divider()

# 環境変数の取得
API_KEY = st.secrets.get("YOUTUBE_API_KEY", os.environ.get("YOUTUBE_API_KEY"))
SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL"))
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", os.environ.get("SUPABASE_KEY"))

supabase_headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# ----------------------------------------------------
# 📚 本格楽曲コンセプト解析辞書 (グループ名完全排除版)
# ----------------------------------------------------
CONCEPT_KEYWORDS = {
    "イージーリスニング・チル": [
        # 音楽・サウンド
        "easy listening", "chill", "lo-fi", "lofi", "acoustic", "soft pop", "mellow", "gentle", "minimal", 
        "ambient", "cozy", "relaxing", "bpm", "piano", "acoustic guitar", "ヒーリング", "チル", 
        "アコースティック", "メロウ", "アンビエント", "癒やし", "穏やか", "スローテンポ", "잔잔한", "편안한", "힐링",
        # テーマ・ビジュアル
        "daily", "bedroom", "morning", "coffee", "walk", "natural", "日常", "散歩", "ベッドルーム", "ナチュラル"
    ],
    "Y2K・レトロアナログ": [
        # 音楽・サウンド
        "y2k", "retro", "nostalgia", "90s", "00s", "80s", "synthwave", "city pop", "eurodance", "uk garage", 
        "jersey club", "2-step", "cassette", "vinyl", "レトロ", "シティポップ", "ユーロダンス", "ジャージークラブ", 
        "カセット", "レコード", "추억", "복고",
        # テーマ・ビジュアル
        "vintage", "analog", "camcorder", "low resolution", "cd player", "flip phone", "8mm",
        "ビンテージ", "アナログ", "ガラケー", "エモい", "レトロフューチャー", "画質"
    ],
    "SF・サイバーパンク": [
        # 音楽・サウンド
        "hyperpop", "futuristic", "metallic", "industrial", "glitch", "distortion", "heavy synth", 
        "ハイパーポップ", "メタリック", "インダストリアル", "グリッチ", "歪み",
        # テーマ・ビジュアル
        "sci-fi", "cyberpunk", "space", "alien", "metaverse", "virtual", "ai", "robot", "android", 
        "dystopia", "portal", "multiverse", "avatar", "サイバーパンク", "宇宙", "近未来", "仮想空間", 
        "ディストピア", "アバター", "異次元", "SF", "우주", "가상"
    ],
    "ガールクラッシュ・ヒップホップ": [
        # 音楽・サウンド
        "trap", "hard brass", "heavy bass", "hiphop", "rap", "powerful", "aggressive", "boombap", 
        "トラップ", "重低音", "爆音", "ブラス", "ラップ", "パワフル", "ドリル",
        # テーマ・ビジュアル
        "girl crush", "badass", "confidence", "queen", "power", "fierce", "bold", "boss", "warrior", 
        "leather", "biker", "ガールクラッシュ", "自信", "強さ", "ボス", "威厳", "革ジャン", "バイカー", "自立", "걸크러시", "당당"
    ],
    "ティーンクラッシュ・ロック": [
        # 音楽・サウンド
        "pop punk", "rock", "electric guitar", "punk", "rebellious", "energetic", "guitar riff", 
        "ポップパンク", "ロック", "エレキギター", "パンク", "ギターリフ",
        # テーマ・ビジュアル
        "teen crush", "rebel", "skater", "gen z", "attitude", "quirky", "rule breaker", 
        "ティーンクラッシュ", "反抗", "スケーター", "Z世代", "個性", "自由奔放", "破天荒", "반항"
    ],
    "エレガント・ロイヤル": [
        # 音楽・サウンド
        "orchestral", "waltz", "strings", "classical", "dramatic pop", "violin", "harpsichord", 
        "オケ", "ヴァイオリン", "ワルツ", "ストリングス", "クラシカル", "クラシック",
        # テーマ・ビジュアル
        "elegant", "royal", "luxury", "ballroom", "crown", "princess", "castle", "chandelier", 
        "jewels", "velvet", "ティアラ", "エレガント", "ロイヤル", "ゴージャス", "貴族", "ドレス", 
        "シャンデリア", "宝石", "華麗", "王族", "우아한", "왕실"
    ],
    "ハイティーン・スクール": [
        # 音楽・サウンド
        "bright pop", "dance pop", "upbeat", "cheerful", "爽快", "ポップ", "明るい",
        # テーマ・ビジュアル
        "high teen", "school", "uniform", "locker", "prom", "cheerleader", "campus", "student", 
        "youth", "crush", "ハイティーン", "制服", "校舎", "ロッカー", "プロム", "チアリーダー", 
        "青春", "初恋", "学園", "학원물", "하이틴"
    ],
    "ダーク・ゴシック・ホラー": [
        # 音楽・サウンド
        "minor key", "gothic", "heavy metal", "dark pop", "eerie", "suspenseful", "organ", 
        "ダークポップ", "重厚", "不穏", "ゴシック", "パイプオルガン",
        # テーマ・ビジュアル
        "dark", "horror", "vampire", "witch", "curse", "nightmare", "mystery", "shadow", 
        "cemetery", "ritual", "blood", "poison", "ホラー", "悪夢", "吸血鬼", "魔女", "呪い", 
        "儀式", "墓地", "ミステリー", "死", "잔혹", "기괴", "어둠"
    ],
    "清純・青春・清涼": [
        # 音楽・サウンド
        "bubblegum pop", "cute synth", "sweet", "bright", "清涼", "さわやか", "スウィート",
        # テーマ・ビジュアル
        "pure", "innocent", "fresh", "cute", "summer", "breeze", "blue sky", "pastel", "flower", 
        "smile", "爽やか", "夏空", "パステル", "初々しい", "清涼感", "清純", "妖精", "청량", "순수"
    ],
    "ディスコ・ファンク": [
        # 音楽・サウンド
        "disco", "funk", "groovy", "brass", "slap bass", "retro dance", "70s", "groove", 
        "ディスコ", "ファンク", "スラップベース", "ブラス", "グルーヴ", "ディスコビート",
        # テーマ・ビジュアル
        "roller skate", "disco ball", "party", "neon", "mirror ball", "dance floor", 
        "ローラースケート", "ミラーボール", "ネオン", "ナイトライフ", "ダンスフロア"
    ]
}

DEFAULT_DATABASE = {
    "Vk5-c_v4gMU": {"concept": "イージーリスニング・チル", "title": "Magnetic"}
}

def extract_video_id(url_or_id):
    url_or_id = url_or_id.strip()
    if len(url_or_id) == 11 and not ("/" in url_or_id or "." in url_or_id):
        return url_or_id
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url_or_id)
    return match.group(1) if match else None

def load_concepts_from_db():
    try:
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/video_concepts?select=*"
        res = requests.get(url, headers=supabase_headers)
        if res.status_code == 200:
            data = res.json()
            if data:
                return {row['video_id']: {"concept": row['concept'], "title": row.get('title', '')} for row in data}
        else:
            st.warning(f"⚠️ DB読み込み警告 ({res.status_code}): {res.text}")
    except Exception as e:
        st.error(f"DB読み込みエラー: {e}")
    
    for vid, info in DEFAULT_DATABASE.items():
        save_concept_to_db(vid, info['concept'], info['title'])
    return DEFAULT_DATABASE.copy()

def save_concept_to_db(video_id, concept, title=""):
    try:
        payload = {
            "video_id": video_id,
            "concept": concept,
            "title": title,
            "updated_at": datetime.now().isoformat()
        }
        headers = supabase_headers.copy()
        headers["Prefer"] = "resolution=merge-duplicates"
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/video_concepts"
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code not in [200, 201]:
            st.error(f"❌ コンセプト保存失敗 ({res.status_code}): {res.text}")
            return False
        return True
    except Exception as e:
        st.error(f"❌ コンセプト保存例外エラー: {e}")
        return False

# ----------------------------------------------------
# 🔍 厳密な属性加重スコアリングエンジン
# ----------------------------------------------------
def auto_detect_concept_dict(video_id):
    try:
        url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}&key={API_KEY}"
        res = requests.get(url).json()
        
        if "items" in res and len(res["items"]) > 0:
            snippet = res["items"][0]["snippet"]
            title = snippet.get("title", "").lower()
            description = snippet.get("description", "").lower()
            tags = [t.lower() for t in snippet.get("tags", [])]
            
            scores = {}
            for concept, keywords in CONCEPT_KEYWORDS.items():
                score = 0
                for kw in keywords:
                    kw_lower = kw.lower()
                    # タイトルに含まれている場合は最重視 (5点)
                    if kw_lower in title:
                        score += 5
                    # 公式タグに含まれている場合 (3点)
                    if any(kw_lower in tag for tag in tags):
                        score += 3
                    # 概要欄に含まれている場合 (1点)
                    if kw_lower in description:
                        score += 1
                if score > 0:
                    scores[concept] = score
            
            # 最高スコアのコンセプトを採用
            if scores:
                best_concept = max(scores, key=scores.get)
                return best_concept, snippet.get("title", "")
            
            return "その他", snippet.get("title", "")
        else:
            st.error("YouTube APIから動画情報を取得できませんでした（URLまたはキーを確認）")
    except Exception as e:
        st.error(f"解析エラー: {e}")
        
    return "その他", ""

def fetch_and_save_data(video_ids):
    if not video_ids: return 0
    ids_str = ",".join(video_ids)
    url = f"https://www.googleapis.com/youtube/v3/videos?part=statistics,snippet&id={ids_str}&key={API_KEY}"
    res = requests.get(url).json()
    success_count = 0
    if "items" in res:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for item in res["items"]:
            payload = {
                "timestamp": now,
                "video_id": item["id"],
                "title": item["snippet"]["title"],
                "views": int(item["statistics"].get('viewCount', 0)),
                "likes": int(item["statistics"].get('likeCount', 0)),
                "comments": 0
            }
            post_res = requests.post(f"{SUPABASE_URL.rstrip('/')}/rest/v1/multi_video_stats", headers=supabase_headers, json=payload)
            if post_res.status_code in [200, 201]:
                success_count += 1
            else:
                st.error(f"❌ 統計データ保存失敗 ({post_res.status_code}): {post_res.text}")
    return success_count


# 📱 画面描画
db_concepts = load_concepts_from_db()

# サイドバー
st.sidebar.header("⚙️ 監視対象の追加")
new_input = st.sidebar.text_input("➕ YouTube動画URL", placeholder="https://www.youtube.com/watch?v=...")

if st.sidebar.button("⚡️ URLから追加"):
    vid = extract_video_id(new_input)
    if vid:
        if vid not in db_concepts:
            with st.sidebar.status("🔍 属性・音楽性キーワードで解析中..."):
                detected_concept, v_title = auto_detect_concept_dict(vid)
                ok = save_concept_to_db(vid, detected_concept, v_title)
                if ok:
                    fetch_and_save_data([vid])
                    st.sidebar.success(f"追加完了: 【{detected_concept}】")
                    st.rerun()
        else:
            st.sidebar.warning("既に存在します。")
    else:
        st.sidebar.error("有効なURLを入力してください。")

st.sidebar.divider()

if st.sidebar.button("🔄 手動で最新データ取得"):
    with st.spinner("最新データを取得中..."):
        cnt = fetch_and_save_data(list(db_concepts.keys()))
    if cnt > 0:
        st.rerun()

# メイン画面
try:
    video_ids = list(db_concepts.keys())
    if video_ids:
        target_url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/multi_video_stats?select=*"
        res = requests.get(target_url, headers=supabase_headers)
        
        if res.status_code == 200 and len(res.json()) == 0:
            with st.spinner("🚀 初回データベースを自動構築中..."):
                fetch_and_save_data(video_ids)
                st.rerun()
                
        elif res.status_code == 200 and len(res.json()) > 0:
            df = pd.DataFrame(res.json())
            df = df[df['video_id'].isin(video_ids)]
            
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                stats_list = []
                
                for vid in video_ids:
                    v_data = df[df['video_id'] == vid].sort_values('timestamp')
                    if not v_data.empty:
                        latest, oldest = v_data.iloc[-1], v_data.iloc[0]
                        clean_title = latest['title'].replace(" '", "").replace("'", "")
                        views, likes = latest['views'], latest['likes']
                        concept = db_concepts[vid]["concept"]
                        
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
                        st.info("※手動で最新データを再取得（更新）すると円グラフが表示されます。")
                
                st.divider()
                
                st.subheader("✏️ コンセプト修正 (手動チューニング・永久保存)")
                all_options = list(CONCEPT_KEYWORDS.keys()) + ["その他"]
                for vid in video_ids:
                    curr_c = db_concepts[vid]["concept"]
                    v_row = stats_df[stats_df['video_id'] == vid]
                    v_title = v_row['タイトル'].values[0] if not v_row.empty else vid
                    
                    idx = all_options.index(curr_c) if curr_c in all_options else len(all_options)-1
                    new_c = st.selectbox(f"🔗 「{v_title}」", all_options, index=idx, key=f"sel_{vid}")
                    
                    if new_c != curr_c:
                        save_concept_to_db(vid, new_c, v_title)
                        st.rerun()
                
                st.divider()
                st.subheader("📊 詳細データ一覧")
                st.dataframe(stats_df.drop(columns=['video_id']).style.format({"累計再生数": "{:,}", "VPH (熱狂度)": "{:,}", "ENG率 (%)": "{:.2f}"}), use_container_width=True)
        else:
             st.error(f"データベース取得エラー ({res.status_code}): {res.text}")
except Exception as e:
    st.error(f"エラー: {e}")
