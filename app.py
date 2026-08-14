import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import re
import os
import altair as alt

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
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# ----------------------------------------------------
# 📚 コンセプト解析辞書 (英語は単語境界で厳密一致、CJKはトラップ除外)
# ----------------------------------------------------
CONCEPT_KEYWORDS = {
   "イージーリスニング・チル": [
        "easy listening", "lofi", "lo-fi", "acoustic", "mellow", 
        "ambient", "cozy", "relaxing", "acoustic guitar", "soothing", 
        "peaceful", "dreamy", "tropical house", "bossa nova", "jazz pop", 
        "neo soul", "ukulele", "midtempo", "falsetto", "soft vocals", "healing",
        "잔잔한", "편안한", "힐링", "어쿠스틱", "자장가", "평화",
        "미니멀", "이지리스닝", "부드러운", "따스한", "차분한",
        "ヒーリング", "アコースティック", "メロウ", "アンビエント", 
        "癒やし", "穏やか", "スローテンポ", "落ち着く", "ゆったり", 
        "眠れる", "心地よい", "のんびり", "そよ風"
    ],
    
    "Y2K・レトロアナログ": [
        "y2k", "retro", "nostalgia", "90s", "00s", "80s", "synthwave", "city pop", "eurodance", 
        "uk garage", "2-step", "cassette", "vinyl", "disco pop", "new jack swing", "boogie", 
        "retro synth", "analog", "camcorder", "cd player", "flip phone", "vintage", "cyber y2k", 
        "millennium", "polaroid", "vhs", "walkman", "pager", "beeper", "gameboy", "arcade", 
        "denim", "low rise", "cargo", "chunky shoes", "lip gloss", "retro future", "synthpop", 
        "vaporwave", "chiptune", "old school", "retro house", "neon retro", "boombox", "mp3 player",
        "추억", "복고", "레트로", "레트로팝", "복고풍", "아날로그", "카세트", "테이프", "레코드", 
        "2000년대", "90년대", "80년대", "갬성", "y2k패션", "옛날", "추억의", "시티팝", "필름", 
        "폴라로이드", "캠코더", "옛날감성", "밀레니엄", "삐삐", "오락실", "데님", "글리터", "세기말", "통바지",
        "レトロ", "シティポップ", "ユーロダンス", "ジャージークラブ", "カセット", "レコード", 
        "ビンテージ", "アナログ", "ガラケー", "エモい", "レトロフューチャー", "90年代", "00年代", 
        "ミレニアム", "フィルム", "ポラロイド", "懐かしい", "平成", "vhs", "ビデオテープ", 
        "ゲームボーイ", "デニム", "カーゴパンツ", "ルーズソックス", "ゲーセン", "ドット絵", "ウォークマン"
    ],


    "SF・サイバーパンク・ハイパーポップ": [
        "sci-fi", "cyberpunk", "alien", "metaverse", "virtual reality", "robot", "android", "dystopia", 
        "portal", "multiverse", "avatar", "hyperpop", "futuristic", "metallic", "glitch", 
        "hologram", "spaceship", "galaxy", "cosmos", "cyber", "matrix", "quantum", "cyborg", 
        "synthcore", "hardstyle", "exoskeleton", "clone", "supernova", "teleport",
        "dimension", "mecha", "nanotech", "time travel",
        "가상현실", "사이버", "인공지능", "로봇", "아바타", "미래도시", "사이버펑크", 
        "메타버스", "글리치", "하이퍼팝", "홀로그램", "디스토피아", "우주선", "은하", "광속", 
        "차원", "외계인", "기계", "크롬", "차원이동", "양자", "오토튠", "실험실",
        "サイバーパンク", "近未来", "仮想空間", "ディストピア", "アバター", "異次元", 
        "メタリック", "インダストリアル", "グリッチ", "歪み", "ハイパーポップ", "ホログラム", "クローム", 
        "ロボット", "人工知能", "未来都市", "電脳", "メタバース", "宇宙船", "異空間", 
        "ワープ", "タイムトラベル", "超次元", "機械仕掛け", "サイボーグ"
    ],
    
    "ガールクラッシュ・ヒップホップ・トラップ": [
        "girl crush", "badass", "confidence", "queen", "power", "fierce", "bold", "boss", "warrior", 
        "leather", "biker", "trap", "hard brass", "heavy bass", "hiphop", "rap", "powerful", 
        "aggressive", "boombap", "drill", "808 bass", "808 drum", "cypher", "freestyle", "flow", 
        "beat", "flex", "money", "swagger", "crown", "throne", "motorcycle", "chain", "tattoo", 
        "dark lip", "boots", "streetwear", "attitude", "dominance", "savage", "independent", 
        "strong woman", "fearless", "flexin", "squad", "gang", "hustle", "bass drop", "baddie",
        "걸크러시", "당당", "걸크러쉬", "카리스마", "힙합", "트랩", "드릴", "래퍼", "랩", "걸파워", 
        "여왕", "강력", "센언니", "보스", "스웨그", "플렉스", "강렬", "가죽", "오토바이", "왕관", "걸크", 
        "자신감", "독보적", "지배", "강한", "독주", "스쿼드", "타투", "체인", "블랙", "비트",
        "ガールクラッシュ", "自信", "強さ", "ボス", "威厳", "革ジャン", "バイカー", "自立", 
        "トラップ", "重低音", "爆音", "ブラス", "ラップ", "パワフル", "ドリル", "カリスマ", "覇権", 
        "王座", "バイク", "ヒップホップ", "スワッグ", "毒舌", "最強", "強い女", "圧倒的", 
        "チェーン", "ストリート", "ブラックコーデ", "タトゥー"
    ],
    
    "ティーンクラッシュ・ポップパンク・ロック": [
        "teen crush", "rebel", "skater", "gen z", "attitude", "quirky", "rule breaker", "pop punk", 
        "rock", "electric guitar", "punk", "rebellious", "energetic", "guitar riff", "garage band", 
        "drum solo", "bass line", "alternative rock", "emo rock", "hard rock", "skateboard", 
        "graffiti", "converse", "leather jacket", "band tee", "headphones", "megaphone", "wild", 
        "loud", "party", "garage", "high energy", "jumping", "mosh", "riot", "dynamic", "youth rebellion", 
        "punk rock", "post punk", "indie rock", "distortion", "misfit", "loud noise", "shout", "scream",
        "틴크러시", "반항", "스케이트", "스케이터", "락", "팝펑크", "일렉기타", "밴드", "제트세대", 
        "자유", "악동", "청춘", "열정", "와일드", "그라피티", "헤드폰", "펑크", "에너지", "개성", 
        "엉뚱", "제멋대로", "락밴드", "소동", "반항아", "메가폰", "난장판", "자유로운", "소리쳐", "광기",
        "ティーンクラッシュ", "反抗", "スケーター", "z世代", "個性", "自由奔放", "破天荒", "ポップパンク", 
        "ロック", "エレキギター", "パンク", "ギターリフ", "自由", "暴れる", "騒々しい", "ギタリスト", 
        "ガレージ", "バンド", "いたずら", "賑やか", "スケボー", "グラフィティ", "メガホン", 
        "ライブハウス", "モッシュ", "叫び", "衝動", "ロックバンド", "アジト", "騒音"
    ],
    
    "エレガント・ロイヤル・クラシック": [
        "elegant", "royal", "luxury", "ballroom", "crown", "princess", "castle", "chandelier", 
        "jewels", "velvet", "tiara", "orchestral", "waltz", "strings", "classical", "dramatic pop", 
        "violin", "harpsichord", "cello", "opera", "symphony", "grand piano", "harp", "masquerade", 
        "banquet", "noble", "aristocracy", "palace", "gold", "silver", "diamond", "silk", "gown", 
        "corsage", "perfume", "antique", "museum", "majesty", "grace", "sophisticated", "regal", 
        "high society", "drama", "cinematic", "epic", "operatic", "baroque", "rococo"
    ],
    
    "ハイティーン・スクール・プレッピー": [
        "high teen", "school", "uniform", "locker", "prom", "cheerleader", "campus", "student", 
        "youth", "bright pop", "dance pop", "upbeat", "cheerful", "classroom", "hallway", "desk", 
        "backpack", "graduation", "varsity", "preppy", "tennis court", "gymnasium", "scoreboard", 
        "letterman jacket", "ribbon", "notebook", "chalk", "cafeteria", "textbook", "yearbook", 
        "confession", "school bus", "teenage", "teen pop", "bubblegum", "high school", "academy", 
        "teenage dream", "youthful", "first love", "after school", "bell", "study hall"
    ],
    
    "ダーク・ゴシック・ホラー・オカルト": [
        "dark", "horror", "vampire", "witch", "curse", "nightmare", "mystery", "shadow", "cemetery", 
        "ritual", "blood", "minor key", "gothic", "heavy metal", "dark pop", "eerie", "suspenseful", 
        "haunted", "ghost", "demon", "skull", "coffin", "moonlight", "dark fantasy", "occult", 
        "spell", "potion", "spider", "bat", "gothic rock", "dark synth", "industrial", "creepy", 
        "thriller", "macabre", "funeral", "grim", "psycho", "possession", "incantation", "labyrinth", 
        "black dress", "raven", "crows", "full moon", "sacrifice", "sinister", "chilling", "spooky"
    ],
    
    "清純・青春・清涼・キュート": [
        "pure", "innocent", "fresh", "cute", "summer", "breeze", "blue sky", "pastel", "flower", 
        "smile", "bubblegum pop", "cute synth", "sweet", "bright", "ocean", "beach", "cloud", 
        "sunshine", "picnic", "garden", "daisy", "cherry blossom", "fairy", "fairy tale", "angel", 
        "soft synth", "sparkling", "innocent love", "heart", "pink", "sky blue", "ribbon", "kitten", 
        "puppy", "white dress", "sunlight", "lemonade", "soda", "sparkling water", "purity", 
        "wholesome", "sweetheart", "bloom", "sunflower", "clear sky", "dazzling", "cotton candy"
    ],
    
    "ディスコ・ファンク・グルーヴ": [
        "disco", "funk", "groovy", "brass", "slap bass", "retro dance", "70s", "groove", 
        "roller skate", "disco ball", "party", "neon", "mirror ball", "dance floor", "funk pop", 
        "disco house", "brass section", "saxophone", "trumpet", "wah guitar", "bassline", "soul", 
        "rhythm", "funky", "glitter", "disco lights", "studio 54", "saturday night", "boogie", 
        "dance party", "night club", "mirrorball", "sequins", "high heels", "roller derby"
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
        requests.post(url, headers=headers, json=payload)
        return True
    except Exception:
        return False

def delete_video_from_db(video_id):
    try:
        url1 = f"{SUPABASE_URL.rstrip('/')}/rest/v1/video_concepts?video_id=eq.{video_id}"
        res1 = requests.delete(url1, headers=supabase_headers)
        
        url2 = f"{SUPABASE_URL.rstrip('/')}/rest/v1/multi_video_stats?video_id=eq.{video_id}"
        res2 = requests.delete(url2, headers=supabase_headers)
        
        return res1.status_code in [200, 204] and res2.status_code in [200, 204]
    except Exception:
        return False

# ----------------------------------------------------
# 単語境界を用いた厳密なマッチング関数
# ----------------------------------------------------
def check_match(kw, text):
    # 英数字のみで構成されている場合は単語境界(\b)を適用
    if re.match(r'^[a-z0-9\s-]+$', kw):
        pattern = r'\b' + re.escape(kw) + r'\b'
        return bool(re.search(pattern, text))
    else:
        # CJK（日本語・韓国語）の場合は通常の部分一致
        return kw in text

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
                    if check_match(kw_lower, title):
                        score += 5
                    if any(check_match(kw_lower, tag) for tag in tags):
                        score += 3
                    if check_match(kw_lower, description):
                        score += 1
                if score > 0:
                    scores[concept] = score
            
            if scores:
                best_concept = max(scores, key=scores.get)
                return best_concept, snippet.get("title", "")
            
            return "その他", snippet.get("title", "")
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
    return success_count


# 画面描画
db_concepts = load_concepts_from_db()

st.sidebar.header("⚙️ 監視対象の追加")
new_input = st.sidebar.text_input("➕ YouTube動画URL", placeholder="https://www.youtube.com/watch?v=...")

if st.sidebar.button("⚡️ URLから追加"):
    vid = extract_video_id(new_input)
    if vid:
        if vid not in db_concepts:
            with st.sidebar.status("解析中..."):
                detected_concept, v_title = auto_detect_concept_dict(vid)
                if save_concept_to_db(vid, detected_concept, v_title):
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

try:
    video_ids = list(db_concepts.keys())
    if video_ids:
        target_url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/multi_video_stats?select=*"
        res = requests.get(target_url, headers=supabase_headers)
        
        if res.status_code == 200 and len(res.json()) == 0:
            with st.spinner("データベース構築中..."):
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
                
                st.subheader("🧩 コンセプト別シェア")
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
                
                st.divider()
                
                st.subheader("🛠️ 動画の管理 (コンセプト修正・削除)")
                all_options = list(CONCEPT_KEYWORDS.keys()) + ["その他"]
                
                for vid in video_ids:
                    curr_c = db_concepts[vid]["concept"]
                    v_row = stats_df[stats_df['video_id'] == vid]
                    v_title = v_row['タイトル'].values[0] if not v_row.empty else db_concepts[vid].get("title", vid)
                    
                    c_select, c_del = st.columns([5, 1])
                    
                    with c_select:
                        idx = all_options.index(curr_c) if curr_c in all_options else len(all_options)-1
                        new_c = st.selectbox(f"🔗 「{v_title}」", all_options, index=idx, key=f"sel_{vid}")
                        if new_c != curr_c:
                            save_concept_to_db(vid, new_c, v_title)
                            st.rerun()
                            
                    with c_del:
                        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                        if st.button("🗑️ 削除", key=f"del_{vid}", type="secondary"):
                            if delete_video_from_db(vid):
                                st.rerun()
                
                st.divider()
                st.subheader("📊 詳細データ一覧")
                st.dataframe(stats_df.drop(columns=['video_id']).style.format({"累計再生数": "{:,}", "VPH (熱狂度)": "{:,}", "ENG率 (%)": "{:.2f}"}), use_container_width=True)
except Exception as e:
    pass
