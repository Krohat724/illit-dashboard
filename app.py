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
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# ----------------------------------------------------
# 📚 超巨大コンセプト解析辞書 (1コンセプトにつき100前後の網羅的キーワード)
# ----------------------------------------------------
CONCEPT_KEYWORDS = {
    "イージーリスニング・チル": [
        "easy listening", "chill", "lofi", "lo-fi", "acoustic", "soft pop", "mellow", "gentle", "minimal", 
        "ambient", "cozy", "relaxing", "piano", "acoustic guitar", "slow", "quiet", "smooth", "soothing", 
        "calm", "breeze", "lazy", "peaceful", "dreamy", "bedroom", "morning", "coffee", "walk", "natural", 
        "study", "sleep", "rest", "healing", "warm", "sunset", "afternoon", "tea", "rain", "window", "pastel", 
        "soft", "house", "deep house", "tropical house", "bossa nova", "jazz pop", "indie pop", "r&b", "neo soul", 
        "ukulele", "rhodes", "electric piano", "midtempo", "whispering", "falsetto", "soft vocals", "light", 
        "comfort", "breathe", "cloud", "blanket", "cappuccino", "book", "garden", "stroll", "whisper", "slumber",
        "잔잔한", "편안한", "힐링", "쉬는날", "커피", "아침", "산책", "따뜻한", "여유", "감성", "카페", "자장가", 
        "평화", "노을", "비오는날", "봄", "바람", "미니멀", "어쿠스틱", "잔잔함", "휴식", "멍때리기", "이지리스닝", 
        "칠", "부드러운", "소소한", "일상", "자연", "침실", "오후", "차한잔", "따스한", "햇살", "차분한", "자장가",
        "ヒーリング", "チル", "アコースティック", "メロウ", "アンビエント", "癒やし", "穏やか", "スローテンポ", 
        "日常", "散歩", "ベッドルーム", "ナチュラル", "落ち着く", "カフェ", "休日", "朝", "ゆったり", "眠れる", 
        "優しい", "ぬくもり", "心地よい", "部屋", "窓辺", "たそがれ", "ほのぼの", "ひだまり", "のんびり", "そよ風"
    ],
    
    "Y2K・レトロアナログ": [
        "y2k", "retro", "nostalgia", "90s", "00s", "80s", "synthwave", "city pop", "eurodance", "uk garage", 
        "2-step", "cassette", "vinyl", "disco pop", "new jack swing", "boogie", "retro synth", "analog", 
        "camcorder", "low resolution", "cd player", "flip phone", "8mm", "vintage", "cyber y2k", "millennium", 
        "1990s", "2000s", "polaroid", "vhs", "vhs effect", "walkman", "pager", "beeper", "gameboy", "arcade", 
        "sticker", "denim", "low rise", "cargo", "butterfly", "chunky shoes", "lip gloss", "glitter", "pixel", 
        "crt", "retro future", "synthpop", "vaporwave", "chiptune", "groove", "funk", "old school", "retro house",
        "cyber", "neon retro", "boombox", "mp3 player", "cyberpunk y2k", "arcade game", "tamagotchi",
        "추억", "복고", "레트로", "레트로팝", "복고풍", "아날로그", "카세트", "테이프", "레코드", "2000년대", 
        "90년대", "80년대", "갬성", "y2k패션", "비디오", "옛날", "추억의", "시티팝", "필름", "폴라로이드", 
        "캠코더", "옛날감성", "밀레니엄", "삐삐", "오락실", "데님", "글리터", "세기말", "감성비디오", "통바지",
        "レトロ", "シティポップ", "ユーロダンス", "ジャージークラブ", "カセット", "レコード", "ビンテージ", 
        "アナログ", "ガラケー", "エモい", "レトロフューチャー", "画質", "90年代", "00年代", "ミレニアム", 
        "フィルム", "ポラロイド", "懐かしい", "平成", "vhs", "ビデオテープ", "ゲームボーイ", "デニム", 
        "カーゴパンツ", "ルーズソックス", "ゲーセン", "シール帳", "ドット絵", "ウォークマン"
    ],
    
   
    
    "ガールクラッシュ・ヒップホップ・トラップ": [
        "girl crush", "badass", "confidence", "queen", "power", "fierce", "bold", "boss", "warrior", 
        "leather", "biker", "trap", "hard brass", "heavy bass", "hiphop", "rap", "powerful", "aggressive", 
        "boombap", "drill", "808 bass", "808 drum", "cypher", "freestyle", "flow", "beat", "flex", "money", 
        "swagger", "crown", "throne", "flames", "fire", "motorcycle", "chain", "tattoo", "dark lip", "boots", 
        "streetwear", "attitude", "dominance", "savage", "unshakeable", "untouchable", "independent", 
        "strong woman", "fearless", "flexin", "squad", "gang", "hustle", "drop", "bass drop", "brass stab", 
        "hard hit", "baddie", "rule the world", "unstoppable", "knockout", "champ", "supremacy", "reign",
        "걸크러시", "당당", "걸크러쉬", "카리스마", "힙합", "트랩", "드릴", "래퍼", "랩", "걸파워", "여왕", 
        "강력", "센언니", "보스", "스웨그", "플렉스", "강렬", "불꽃", "가죽", "오토바이", "왕관", "걸크", 
        "자신감", "카리스마", "독보적", "지배", "강한", "독주", "스쿼드", "타투", "체인", "블랙", "비트",
        "ガールクラッシュ", "自信", "強さ", "ボス", "威厳", "革ジャン", "バイカー", "自立", "トラップ", 
        "重低音", "爆音", "ブラス", "ラップ", "パワフル", "ドリル", "カリスマ", "覇権", "王座", "炎", 
        "バイク", "ヒップホップ", "スワッグ", "毒舌", "最強", "強い女", "屈しない", "圧倒的", "チェーン", 
        "ストリート", "ブラックコーデ", "タトゥー", "ノーコンプレックス"
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
    
    "ティーンクラッシュ・ポップパンク・ロック": [
        "teen crush", "rebel", "skater", "gen z", "attitude", "quirky", "rule breaker", "pop punk", "rock", 
        "electric guitar", "punk", "rebellious", "energetic", "guitar riff", "garage band", "drum solo", 
        "bass line", "alternative rock", "emo rock", "hard rock", "skateboard", "graffiti", "converse", 
        "leather jacket", "band tee", "headphones", "megaphone", "wild", "free", "loud", "party", "basement", 
        "garage", "high energy", "jumping", "mosh", "riot", "dynamic", "youth rebellion", "crazy", "messy", 
        "fun", "chaos", "punk rock", "post punk", "indie rock", "distortion guitar", "rebel heart", "freak", 
        "outcast", "misfit", "loud noise", "shout", "scream", "smash", "boom", "wreck",
        "틴크러시", "반항", "스케이트", "스케이터", "락", "팝펑크", "일렉기타", "밴드", "제트세대", "자유", 
        "장난", "악동", "청춘", "열정", "와일드", "그라피티", "헤드폰", "펑크", "에너지", "개성", "엉뚱", 
        "제멋대로", "락밴드", "소동", "반항아", "메가폰", "난장판", "자유로운", "소리쳐", "광기", "파티",
        "ティーンクラッシュ", "反抗", "スケーター", "z世代", "個性", "自由奔放", "破天荒", "ポップパンク", 
        "ロック", "エレキギター", "パンク", "ギターリフ", "自由", "暴れる", "騒々しい", "ギタリスト", 
        "ガレージ", "バンド", "いたずら", "賑やか", "スケボー", "グラフィティ", "メガホン", "ライブハウス", 
        "モッシュ", "叫び", "衝動", "ロックバンド", "アジト", "騒音"
    ],
    
    "エレガント・ロイヤル・クラシック": [
        "elegant", "royal", "luxury", "ballroom", "crown", "princess", "castle", "chandelier", "jewels", 
        "velvet", "tiara", "orchestral", "waltz", "strings", "classical", "dramatic pop", "violin", "harpsichord", 
        "cello", "opera", "symphony", "grand piano", "harp", "masquerade", "banquet", "queen", "noble", 
        "aristocracy", "palace", "gold", "silver", "diamond", "silk", "gown", "corsage", "perfume", "antique", 
        "museum", "majesty", "grace", "sophisticated", "regal", "high society", "drama", "cinematic", "epic", 
        "operatic", "baroque", "rococo", "majestical", "splendid", "fairytale castle", "glass slipper",
        "우아한", "왕실", "공주", "여왕", "왕관", "궁전", "드레스", "고풍", "클래식", "샹들리에", "오케스트라", 
        "바이올린", "왈츠", "귀족", "무도회", "자수", "보석", "다이아몬드", "고급", "럭셔리", "로얄", "대저택", 
        "벨벳", "마스커레이드", "화려한", "장엄한", "품격", "영주", "하프", "고전적", "상류사회", "드라마틱",
        "ティアラ", "エレガント", "ロイヤル", "ゴージャス", "貴族", "ドレス", "シャンデリア", "宝石", 
        "華麗", "王族", "オケ", "ヴァイオリン", "ワルツ", "ストリングス", "クラシカル", "クラシック", 
        "お城", "豪華", "舞踏会", "王冠", "豪華絢爛", "高級感", "シルク", "オーケストラ", "宮殿", 
        "アンティーク", "ドレスアップ", "上品", "気品", "シンフォニー", "オペラ", "気高く"
    ],
    
    "ハイティーン・スクール・プレッピー": [
        "high teen", "school", "uniform", "locker", "prom", "cheerleader", "campus", "student", "youth", 
        "crush", "bright pop", "dance pop", "upbeat", "cheerful", "classroom", "hallway", "desk", "backpack", 
        "graduation", "varsity", "preppy", "tennis court", "gymnasium", "scoreboard", "letterman jacket", 
        "ribbon", "notebook", "chalk", "cafeteria", "textbook", "yearbook", "confession", "school bus", 
        "teenage", "teen pop", "bubblegum", "high school", "academy", "teenage dream", "youthful", 
        "first love", "after school", "bell", "study hall", "school life", "classmate", "crush on you",
        "하이틴", "학원물", "학교", "교복", "로커", "체육관", "테니스", "교실", "친구", "동아리", "졸업", 
        "스쿨", "틴에이저", "청춘", "고등학생", "여고생", "남고생", "방과후", "학창시절", "고교", "첫사랑", 
        "학창", "러브레터", "칠판", "책상", "스쿨버스", "교복패션", "프롬", "치어리더", "짝사랑",
        "ハイティーン", "制服", "校舎", "ロッカー", "プロム", "チアリーダー", "青春", "初恋", "学園", 
        "学園もの", "校庭", "テニス", "テニスウェア", "教室", "放課後", "恋心", "告白", "友達", 
        "部活", "クラブ活動", "サークル", "卒業式", "クラスメイト", "黒板", "通学", "スクールバス", 
        "ラブレター", "青い春", "甘酸っぱい", "甘い初恋"
    ],
    
    "ダーク・ゴシック・ホラー・オカルト": [
        "dark", "horror", "vampire", "witch", "curse", "nightmare", "mystery", "shadow", "cemetery", 
        "ritual", "blood", "poison", "minor key", "gothic", "heavy metal", "dark pop", "eerie", "suspenseful", 
        "organ", "haunted", "ghost", "demon", "skull", "coffin", "moonlight", "dark fantasy", "occult", 
        "spell", "potion", "spider", "bat", "gothic rock", "dark synth", "industrial", "creepy", "thriller", 
        "macabre", "funeral", "grim", "psycho", "possession", "incantation", "labyrinth", "black dress", 
        "raven", "crows", "full moon", "sacrifice", "sinister", "chilling", "fright", "spooky", "graveyard",
        "어둠", "공포", "호러", "뱀파이어", "마녀", "저주", "악몽", "미스터리", "그림자", "공동묘지", "의식", 
        "피", "독", "잔혹", "기괴", "고딕", "오컬트", "유령", "해골", "마법", "악마", "스릴러", "기괴함", 
        "다크", "밤", "흑마술", "괴물", "유령의집", "흡혈귀", "주문", "붉은달", "지옥", "잔혹한",
        "ホラー", "悪夢", "吸血鬼", "魔女", "呪い", "儀式", "墓地", "ミステリー", "死", "ダークポップ", 
        "重厚", "不穏", "ゴシック", "パイプオルガン", "サスペンス", "オカルト", "棺桶", "骸骨", "血", 
        "毒", "漆黒", "黒魔術", "闇", "不気味", "惨劇", "ヴァンパイア", "悪魔", "怪奇", "ホラー映画", 
        "心霊", "スリラー", "恐怖", "異形"
    ],
    
    "清純・青春・清涼・キュート": [
        "pure", "innocent", "fresh", "cute", "summer", "breeze", "blue sky", "pastel", "flower", "smile", 
        "bubblegum pop", "cute synth", "sweet", "bright", "ocean", "sea", "beach", "cloud", "sunshine", 
        "picnic", "garden", "daisy", "cherry blossom", "fairy", "fairy tale", "angel", "soft synth", 
        "sparkling", "innocent love", "heart", "pink", "sky blue", "ribbon", "kitten", "puppy", "white dress", 
        "sunlight", "lemonade", "soda", "sparkling water", "purity", "wholesome", "sweetheart", "bloom", 
        "sunflower", "clear sky", "dazzling", "gentle breeze", "cotton candy", "bubble",
        "청량", "순수", "상큼", "청순", "청춘", "여름", "미소", "바다", "하늘", "파스텔", "꽃", "요정", 
        "엔젤", "햇살", "설렘", "아이돌", "귀여운", "달콤", "사랑스러운", "봄바람", "피크닉", "수줍은", 
        "청초", "풋풋", "비타민", "상쾌한", "탄산", "레모네이드", "해바라기", "하늘색", "첫사랑감성",
        "爽やか", "夏空", "パステル", "初々しい", "清涼感", "清純", "妖精", "青春", "キュート", 
        "さわやか", "スウィート", "海", "ひまわり", "青空", "風", "笑顔", "恋模様", "パステルカラー", 
        "桜", "お花畑", "レモネード", "炭酸", "天使", "ときめき", "ピュア", "透明感", "甘酸っぱい", 
        "ひだまり", "ルンルン", "可愛らしい"
    ],
    
    "ディスコ・ファンク・グルーヴ": [
        "disco", "funk", "groovy", "brass", "slap bass", "retro dance", "70s", "groove", "roller skate", 
        "disco ball", "party", "neon", "mirror ball", "dance floor", "funk pop", "disco house", "brass section", 
        "saxophone", "trumpet", "wah guitar", "bassline", "soul", "rhythm", "funky", "glitter", "disco lights", 
        "studio 54", "saturday night", "boogie", "boogie woogie", "dance party", "night club", "mirrorball", 
        "sequins", "high heels", "roller derby", "get down", "funkytown", "grooviest", "uptown funk",
        "디스코", "펑크", "그루브", "나이트", "복고댄스", "미러볼", "댄스플로어", "롤러스케이트", "파티", 
        "네온사인", "70년대", "펑키", "디스코팝", "섹소폰", "브라스", "흥", "댄스파티", "신나는", "밤", 
        "클럽", "화려한", "들썩이는", "리듬감", "나이트클럽", "화려한조명", "파티타임",
        "ディスコ", "ファンク", "スラップベース", "ブラス", "グルーヴ", "ディスコビート", "ローラースケート", 
        "ミラーボール", "ネオン", "ナイトライフ", "ダンスフロア", "70年代", "セクシー", "ノリノリ", 
        "パーティー", "ソウル", "サックス", "トランペット", "踊る", "夜遊び", "クラブ", "ファンキー", 
        "フィーバー", "ソウルフル", "ダンサブル", "夜の街"
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
# 🗑️ Supabaseからの完全データ削除関数
# ----------------------------------------------------
def delete_video_from_db(video_id):
    try:
        # 1. video_concepts から削除
        url1 = f"{SUPABASE_URL.rstrip('/')}/rest/v1/video_concepts?video_id=eq.{video_id}"
        res1 = requests.delete(url1, headers=supabase_headers)
        
        # 2. multi_video_stats から削除
        url2 = f"{SUPABASE_URL.rstrip('/')}/rest/v1/multi_video_stats?video_id=eq.{video_id}"
        res2 = requests.delete(url2, headers=supabase_headers)
        
        if res1.status_code in [200, 204] and res2.status_code in [200, 204]:
            return True
        else:
            st.error(f"❌ 削除失敗: concepts({res1.status_code}), stats({res2.status_code})")
            return False
    except Exception as e:
        st.error(f"❌ 削除例外エラー: {e}")
        return False

# ----------------------------------------------------
# 🔍 1,000単語超え・精密加重判定エンジン
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
                    if kw_lower in title:
                        score += 5
                    if any(kw_lower in tag for tag in tags):
                        score += 3
                    if kw_lower in description:
                        score += 1
                if score > 0:
                    scores[concept] = score
            
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
            with st.sidebar.status("🔍 巨大辞書（1,000語超）で精密解析中..."):
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
                
                # 🛠️ コンセプト修正 & 削除セクション
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
                                st.toast(f"🗑️ 「{v_title}」を削除しました")
                                st.rerun()
                
                st.divider()
                st.subheader("📊 詳細データ一覧")
                st.dataframe(stats_df.drop(columns=['video_id']).style.format({"累計再生数": "{:,}", "VPH (熱狂度)": "{:,}", "ENG率 (%)": "{:.2f}"}), use_container_width=True)
        else:
             st.error(f"データベース取得エラー ({res.status_code}): {res.text}")
    else:
        st.info("監視対象の動画がありません。サイドバーからYouTube URLを追加してください。")
except Exception as e:
    st.error(f"エラー: {e}")
