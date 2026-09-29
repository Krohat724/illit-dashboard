import os
import re
import requests
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime, timezone
import google.generativeai as genai

# YouTube URLから Video ID (11桁の識別子) を抽出する関数（先頭付近に配置）
def extract_video_id(url):
    if not url or not isinstance(url, str):
        return None
    
    patterns = [
        r"(?:v=|\/v\/|embed\/|shorts\/)([0-9A-Za-z_-]{11})",
        r"youtu\.be\/([0-9A-Za-z_-]{11})"
    ]
    for pattern in patterns:
        match = re.search(pattern, url.strip())
        if match:
            return match.group(1)
            
    if len(url.strip()) == 11 and re.match(r"^[0-9A-Za-z_-]{11}$", url.strip()):
        return url.strip()
        
    return None

# ==========================================
# 0. ページ基本設定 & カスタムCSS
# ==========================================
st.set_page_config(
    page_title="K-POP/J-POP 競合バズ解析 SaaS",
    layout="wide"
)

st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        border-left: 5px solid #FF4B4B;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stAlert { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. APIキー & Supabase接続の初期化
# ==========================================
YOUTUBE_API_KEY = st.secrets.get("YOUTUBE_API_KEY", "")
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "Application/json"
}

# 動画タイトルから「曲名 / アーティスト名」を自動抽出する関数（Unknown化絶対防止版）
def clean_title(title, max_len=26):
    if title is None or pd.isna(title):
        return "Unknown"
    
    title_str = str(title).strip()
    if not title_str or title_str.lower() in ["none", "nan", "unknown"]:
        return "Unknown"

    cleaned_title = title_str

    # 不要な【MV】や [Official MV] 等の装飾を削除
    try:
        cleaned_title = re.sub(
            r"[【\[\(\{\<]\s*(Official\s*)?(MV|Music Video|Performance Video|Dance Practice|Audio|Special Video)\s*(full)?\s*[】\]\)\}\>]",
            "",
            cleaned_title,
            flags=re.IGNORECASE
        )
        remove_words = [
            "Official MV", "Official Music Video", "MUSIC VIDEO", "MV full", "MV", 
            "(Official)", "Performance Video", "Official Audio", "Dance Practice"
        ]
        for w in remove_words:
            cleaned_title = re.sub(re.escape(w), "", cleaned_title, flags=re.IGNORECASE)
    except Exception:
        pass

    song_title = None
    artist_name = None

    # 『』, 「」, '', "" の括弧から「曲名」を抜き出す
    brackets_patterns = [
        r"『([^』]+)』",
        r"「([^」]+)」",
        r"'([^']+)'",
        r'"([^"]+)"'
    ]

    for pattern in brackets_patterns:
        try:
            match = re.search(pattern, cleaned_title)
            if match:
                song_title = match.group(1).strip()
                remaining = cleaned_title.replace(match.group(0), "").strip()
                
                # 残り文字からアーティスト名を抽出
                remaining = re.sub(r"\b\d+(st|nd|rd|th)?\s*(Single|Album|EP)\b", "", remaining, flags=re.IGNORECASE)
                remaining = re.sub(r"[【】\[\]\(\)\{\}\<\>／/\|\-\–\—]", " ", remaining)
                remaining = re.sub(r"\s+", " ", remaining).strip()
                
                if remaining:
                    artist_name = remaining
                break
        except Exception:
            pass

    # 括弧がない場合は / や - で分割
    if not song_title:
        for sep in ["/", "-", "|", "／"]:
            if sep in cleaned_title:
                parts = [p.strip() for p in cleaned_title.split(sep) if p.strip()]
                if len(parts) >= 2:
                    artist_name = re.sub(r"[【】\[\]\(\)\{\}\<\>]", "", parts[0]).strip()
                    song_title = parts[-1]
                    break
        if not song_title:
            song_title = cleaned_title.strip()

    if artist_name:
        artist_name = re.sub(r"[【】\[\]\(\)\{\}\<\>]", "", artist_name).strip()

    # 「曲名 / アーティスト名」にフォーマット
    if song_title and artist_name and artist_name.lower() not in ["official", "mv"]:
        result = f"{song_title} / {artist_name}"
    elif song_title:
        result = song_title
    else:
        result = title_str

    if len(result) > max_len:
        return result[:max_len] + "…"
    return result

# YouTube URLから Video ID (11桁の識別子) を抽出する関数
def extract_video_id(url):
    if not url or not isinstance(url, str):
        return None
    
    # normal: https://www.youtube.com/watch?v=XXXXXXXXXXX
    # short: https://youtu.be/XXXXXXXXXXX
    # shorts: https://www.youtube.com/shorts/XXXXXXXXXXX
    patterns = [
        r"(?:v=|\/v\/|embed\/|shorts\/)([0-9A-Za-z_-]{11})",
        r"youtu\.be\/([0-9A-Za-z_-]{11})"
    ]
    for pattern in patterns:
        match = re.search(pattern, url.strip())
        if match:
            return match.group(1)
            
    # URLではなくIDそのものが直接入力された場合のフォールバック
    if len(url.strip()) == 11 and re.match(r"^[0-9A-Za-z_-]{11}$", url.strip()):
        return url.strip()
        
    return None

# YouTube APIから snippet を自動取得
@st.cache_data(ttl=3600)
def fetch_video_snippets(v_ids, api_key):
    info_map = {}
    if not v_ids or not api_key:
        return info_map
    try:
        url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={','.join(v_ids)}&key={api_key}"
        res = requests.get(url).json()
        for item in res.get("items", []):
            snippet = item.get("snippet", {})
            info_map[item["id"]] = {
                "title": snippet.get("title", "Unknown"),
                "published_at": snippet.get("publishedAt")
            }
    except Exception:
        pass
    return info_map

# Supabase未保存動画の即時ライブ取得
def fetch_live_video_stats(v_ids, api_key):
    live_data = {}
    if not v_ids or not api_key:
        return live_data
    try:
        url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&id={','.join(v_ids)}&key={api_key}"
        res = requests.get(url).json()
        for item in res.get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            live_data[item["id"]] = {
                "title": snippet.get("title", "Unknown"),
                "published_at": snippet.get("publishedAt"),
                "views": int(stats.get("viewCount", 0)),
                "likes": int(stats.get("likeCount", 0)),
                "comments": int(stats.get("commentCount", 0))
            }
    except Exception:
        pass
    return live_data

# Supabase全データ取得
@st.cache_data(ttl=60)
def load_supabase_data():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return pd.DataFrame()
    try:
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/multi_video_stats?select=*"
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            return pd.DataFrame(res.json())
    except Exception:
        pass
    return pd.DataFrame()

# ==========================================
# 2. サイドバー：一括URL入力（状態保持 & 更新ボタン付き）
# ==========================================
st.sidebar.title(" 競合トラッキング設定")

#  手動更新ボタン（押すとキャッシュをクリアして最新データをYouTubeから再取得）
if st.sidebar.button(" 最新データに手動更新", use_container_width=True):
    st.cache_data.clear()
    st.sidebar.success("最新データを再取得しました！")

st.sidebar.markdown("監視したい競合MVのURLを一括入力してください**（最大15本・改行区切り）**")

# Session StateでURL入力内容を記憶（画面更新でも消えない）
if "saved_urls_text" not in st.session_state:
    st.session_state.saved_urls_text = ""

urls_text = st.sidebar.text_area(
    "YouTube URL 一括入力",
    value=st.session_state.saved_urls_text,
    height=180,
    placeholder="https://www.youtube.com/watch?v=...\nhttps://www.youtube.com/watch?v=...",
    key="url_text_area"
)

# 入力内容を保存
st.session_state.saved_urls_text = urls_text

raw_urls = [u.strip() for u in urls_text.split("\n") if u.strip()]
video_ids = []
for u in raw_urls[:15]:
    v_id = extract_video_id(u)
    if v_id and v_id not in video_ids:
        video_ids.append(v_id)

st.sidebar.caption(f"現在の比較対象: **{len(video_ids)}本** / 最大15本")

# 自動登録処理
if video_ids and SUPABASE_URL and SUPABASE_KEY:
    for v_id in video_ids:
        try:
            track_url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/tracked_videos"
            track_headers = {**headers, "Prefer": "resolution=ignore-duplicates"}
            requests.post(track_url, headers=track_headers, json={"video_id": v_id})
        except Exception:
            pass

# ==========================================
# 3. メイン画面ヘッダー
# ==========================================
st.title("バズ解析ダッシュボード")
st.caption("リアルタイムのバズ勢い × 投稿日時の勝ちパターン分析 SaaS")

df_all = load_supabase_data()

if len(video_ids) == 0:
    st.info("👈 サイドバーに比較したいYouTube動画のURLを貼り付けてください（複数入力可能）。")
    st.stop()

df_filtered = df_all[df_all['video_id'].isin(video_ids)].copy() if not df_all.empty else pd.DataFrame()

if not df_filtered.empty:
    df_filtered['timestamp'] = pd.to_datetime(df_filtered['timestamp'], utc=True)
    if 'published_at' in df_filtered.columns:
        df_filtered['published_at'] = pd.to_datetime(df_filtered['published_at'], utc=True)

now_utc = datetime.now(timezone.utc)

# ==========================================
# 4. 指標計算ロジック（分かりやすい言葉に変換）
# ==========================================
summary_data = []

missing_vids = [v for v in video_ids if df_filtered.empty or df_filtered[df_filtered['video_id'] == v].empty]
live_stats = fetch_live_video_stats(missing_vids, YOUTUBE_API_KEY) if missing_vids else {}

for v_id in video_ids:
    df_v = df_filtered[df_filtered['video_id'] == v_id].sort_values('timestamp') if not df_filtered.empty else pd.DataFrame()
    
    if df_v.empty:
        if v_id in live_stats:
            ls = live_stats[v_id]
            full_title = ls['title']
            short_title = clean_title(full_title)
            views = ls['views']
            pub_at = pd.to_datetime(ls['published_at'], utc=True)
            pub_at_jst = pub_at.tz_convert('Asia/Tokyo')
            
            lifetime_hours = max((now_utc - pub_at).total_seconds() / 3600, 0.1)
            lifetime_vph = round(views / lifetime_hours, 1)
            current_vph = lifetime_vph
            momentum_ratio = 1.0
            likes = ls.get('likes', 0)
            comments = ls.get('comments', 0)
            like_rate = round((likes / views) * 100, 2) if views > 0 else 0
            comment_rate = round((comments / views) * 100, 3) if views > 0 else 0
            engagement_rate = round(((likes + comments) / views) * 100, 2) if views > 0 else 0
            
            summary_data.append({
                "video_id": v_id,
                "full_title": full_title,
                "short_title": short_title,
                "views": views,
                "likes": likes,
                "comments": comments,
                "like_rate": like_rate,           # 高評価率 (%)
                "comment_rate": comment_rate,     # コメント率 (%)
                "engagement_rate": engagement_rate, # 総合熱量 (%)
                "published_at_jst": pub_at_jst,
                "lifetime_hours": round(lifetime_hours, 1),
                "lifetime_vph": lifetime_vph,
                "current_vph": current_vph,
                "momentum_ratio": momentum_ratio,
                "pub_day": pub_at_jst.strftime('%A'),
                "pub_hour": pub_at_jst.hour
            })
        continue

    latest_row = df_v.iloc[-1]
    first_row = df_v.iloc[0]
    
    
    # 蓄積データからタイトルを取得（空・NaN・Unknownの場合はYouTube APIから強制取得して補填）
    full_title = latest_row.get('title')
    if pd.isna(full_title) or not full_title or str(full_title).lower() in ['none', 'nan', 'unknown']:
        snippets = fetch_video_snippets([v_id], YOUTUBE_API_KEY)
        full_title = snippets.get(v_id, {}).get('title', 'Unknown')
        
    short_title = clean_title(full_title)
    views = int(latest_row.get('views', latest_row.get('view_count', 0)))
    
    pub_at_raw = latest_row.get('published_at')
    if pd.isna(pub_at_raw) or str(pub_at_raw) == 'None':
        snippets = fetch_video_snippets([v_id], YOUTUBE_API_KEY)
        pub_at_raw = snippets.get(v_id, {}).get('published_at', now_utc.isoformat())
        
    pub_at = pd.to_datetime(pub_at_raw, utc=True)
    pub_at_jst = pub_at.tz_convert('Asia/Tokyo')
    
    lifetime_hours = max((now_utc - pub_at).total_seconds() / 3600, 0.1)
    lifetime_vph = round(views / lifetime_hours, 1)

    # ==========================================
    # ▼▼▼ 修正・上書きする部分 ▼▼▼
    # ==========================================
    # ① 通算ヒットペース (Lifetime VPH)
    lifetime_hours = max((now_utc - pub_at).total_seconds() / 3600, 0.1)
    lifetime_vph = round(views / lifetime_hours, 1)
    
    # ② 現在のバズ勢い (直近最大24時間の「瞬間風速」に超高感度化)
    latest_time = latest_row['timestamp']
    recent_df = df_v[df_v['timestamp'] >= (latest_time - pd.Timedelta(hours=24))]
    
    past_row = None
    if len(recent_df) > 1:
        past_row = recent_df.iloc[0] # 最大24時間前のデータと比較
    elif len(df_v) > 1:
        past_row = df_v.iloc[-2]     # 24時間以内のデータがない場合は直近1つ前と比較
        
    if past_row is not None:
        tracking_hours = (latest_time - past_row['timestamp']).total_seconds() / 3600
        # 3分(0.05時間)以上のデータ間隔があれば「今の時速」を計算
        if tracking_hours > 0.05:  
            past_views = int(past_row.get('views', past_row.get('view_count', 0)))
            current_vph = round((views - past_views) / tracking_hours, 1)
        else:
            current_vph = lifetime_vph
    else:
        current_vph = lifetime_vph
        
    momentum_ratio = round(current_vph / lifetime_vph, 2) if lifetime_vph > 0 else 1.0
    # ==========================================
    # ▲▲▲ 修正・上書きここまで ▲▲▲
    # ==========================================
    
    tracking_hours = (latest_row['timestamp'] - first_row['timestamp']).total_seconds() / 3600
    if tracking_hours > 0.1:
        views_diff = views - int(first_row.get('views', first_row.get('view_count', 0)))
        current_vph = round(views_diff / tracking_hours, 1)
    else:
        current_vph = lifetime_vph
        
    momentum_ratio = round(current_vph / lifetime_vph, 2) if lifetime_vph > 0 else 1.0
    likes = int(latest_row.get('likes', 0))
    comments = int(latest_row.get('comments', 0))
    like_rate = round((likes / views) * 100, 2) if views > 0 else 0
    comment_rate = round((comments / views) * 100, 3) if views > 0 else 0
    engagement_rate = round(((likes + comments) / views) * 100, 2) if views > 0 else 0
    
    summary_data.append({
        "video_id": v_id,
        "full_title": full_title,
        "short_title": short_title,
        "views": views,
        "likes": likes,
        "comments": comments,
        "like_rate": like_rate,           # 高評価率 (%)
        "comment_rate": comment_rate,     # コメント率 (%)
        "engagement_rate": engagement_rate, # 総合熱量 (%)
        "published_at_jst": pub_at_jst,
        "lifetime_hours": round(lifetime_hours, 1),
        "lifetime_vph": lifetime_vph,
        "current_vph": current_vph,
        "momentum_ratio": momentum_ratio,
        "pub_day": pub_at_jst.strftime('%A'),
        "pub_hour": pub_at_jst.hour
    })

if summary_data:
    df_summary = pd.DataFrame(summary_data)
else:
    st.warning(" 有効なYouTube URLを入力してください。")
    st.stop()

# ==========================================
# 機能 1:  VPHモメンタム比較
# ==========================================
st.subheader("1. VPHモメンタム比較")
st.markdown("""
* **通算ヒットペース（平均時速）**: 動画公開から現在までの平均伸び速度
* **現在のバズ勢い（直近時速）**: ツールに登録後のリアルタイム増加速度（今まさにバズっているか）
""")

col1, col2 = st.columns([2, 1])

with col1:
    fig_vph = go.Figure()
    fig_vph.add_trace(go.Bar(
        x=df_summary['short_title'],
        y=df_summary['lifetime_vph'],
        name='平均の伸び具合',
        marker_color='#1f77b4',
        hovertext=df_summary['full_title']
    ))
    fig_vph.add_trace(go.Bar(
        x=df_summary['short_title'],
        y=df_summary['current_vph'],
        name='現在のバズ勢い ',
        marker_color='#ff7f0e',
        hovertext=df_summary['full_title']
    ))
    fig_vph.update_layout(
        barmode='group',
        title="動画別 再生速度（VPH）比較",
        xaxis_title="動画タイトル",
        yaxis_title="再生増加数 (回 / 時間)",
        legend=dict(orientation="h", y=1.1)
    )
    st.plotly_chart(fig_vph, use_container_width=True)

with col2:
    st.markdown("#####  バズ加速率判定")
    for _, row in df_summary.iterrows():
        status = " 急加速中" if row['momentum_ratio'] > 1.2 else (" 減速傾向" if row['momentum_ratio'] < 0.8 else " 安定維持")
        st.write(f"**{row['short_title']}**")
        st.caption(f"バズ加速率: **{row['momentum_ratio']}倍** ({status})")
        st.write(f"・直近速度: `{row['current_vph']:,} 回/時`")
        st.write(f"・通算平均: `{row['lifetime_vph']:,} 回/時`")
        st.divider()

# ==========================================
# 機能 2:  競合新曲 Launch Tracker（初速レーダー）
# ==========================================
st.subheader("2. 新曲リリース自動追跡")
st.caption("公開直後（72時間以内）の新曲MVを自動検知し、初期ロケットスタートの伸びを監視")

df_new_releases = df_summary[df_summary['lifetime_hours'] <= 72]

if not df_new_releases.empty:
    st.success(f" 比較対象に **{len(df_new_releases)}本** の新曲（公開72時間以内）を検知しました！")
    cols = st.columns(min(len(df_new_releases), 4))
    for idx, (_, row) in enumerate(df_new_releases.iterrows()):
        with cols[idx % 4]:
            st.metric(
                label=f" {row['short_title']}",
                value=f"{row['views']:,} 回",
                delta=f"初速 {row['lifetime_vph']:,} 回/時"
            )
            st.caption(f" 公開: {row['published_at_jst'].strftime('%m/%d %H:%M')} (経過: {row['lifetime_hours']}h)")
else:
    st.info("選択中の動画の中に公開72時間以内の『新曲』はありません。新曲URLを事前に登録しておくと公開直後からの初速ペースが自動記録されます。")

# ==========================================
# 機能 3:  投稿日時 × バズ速度マトリクス（勝ちパターン分析）
# ==========================================
st.subheader("3. ベスト投稿日時アナリティクス")
st.markdown("競合動画の `公開曜日` と `公開時間帯（日本時間 JST）` を分析し、**どのタイミングで出された動画が最も高い伸び（通算ヒットペース）を記録しているか** を可視化します。")

days_jp = {'Monday':'月', 'Tuesday':'火', 'Wednesday':'水', 'Thursday':'木', 'Friday':'金', 'Saturday':'土', 'Sunday':'日'}
df_summary['pub_day_jp'] = df_summary['pub_day'].map(days_jp)

matrix_df = df_summary.pivot_table(
    index='pub_day_jp',
    columns='pub_hour',
    values='lifetime_vph',
    aggfunc='mean'
).fillna(0)

if not matrix_df.empty:
    fig_matrix = px.imshow(
        matrix_df,
        labels=dict(x="公開時間帯 (時)", y="公開曜日", color="通算平均伸び (回/時)"),
        x=[f"{h}時" for h in matrix_df.columns],
        title="投稿タイミング別 平均ヒットペース ヒートマップ",
        color_continuous_scale="Reds"
    )
    st.plotly_chart(fig_matrix, use_container_width=True)
    
    best_row = df_summary.loc[df_summary['lifetime_vph'].idxmax()]
    st.success(f" **競合の最高ヒットタイミング分析結果**\n\n"
               f"最も高い初速・伸び（`{best_row['lifetime_vph']:,} 回/時`）を記録しているのは **『{best_row['pub_day_jp']}曜日の {best_row['pub_hour']}時』** に公開された動画（`{best_row['full_title']}`）です！")
# ==========================================
# 機能 4:  ファンダム熱量（エンゲージメント分析）
# ==========================================
st.subheader("4. ファンダム熱量スコア")
st.markdown("""
再生数に対する **高評価率（高評価÷再生数）** と **コメント率（コメント÷再生数）** を数値化し、ファンの「熱狂度（コアファンの濃さ）」を分析します。
* **高評価率**: 楽曲やMVに対するポジティブな支持（目安: 2.0%以上で高評価）
* **コメント率**: ファンダムの熱量・口コミ拡散力（目安: 0.05%以上で熱狂的ファン多数）
""")

col_eng1, col_eng2 = st.columns([2, 1])

with col_eng1:
    # 高評価率とコメント率の比較グラフ
    fig_eng = go.Figure()
    fig_eng.add_trace(go.Bar(
        x=df_summary['short_title'],
        y=df_summary['like_rate'],
        name='高評価率 (%)',
        marker_color='#FF4B4B',
        hovertext=df_summary['full_title']
    ))
    fig_eng.add_trace(go.Bar(
        x=df_summary['short_title'],
        y=df_summary['comment_rate'],
        name='コメント率 (%)',
        marker_color='#00CC96',
        hovertext=df_summary['full_title']
    ))
    fig_eng.update_layout(
        barmode='group',
        title="動画別 エンゲージメント率（ファンダム反応率）比較",
        xaxis_title="動画タイトル",
        yaxis_title="割合 (%)",
        legend=dict(orientation="h", y=1.1)
    )
    st.plotly_chart(fig_eng, use_container_width=True)

with col_eng2:
    st.markdown("#####  コアファン濃度診断")
    for _, row in df_summary.iterrows():
        # 熱量ランク判定
        if row['engagement_rate'] >= 3.0:
            rank = " 超熱狂ファンダム (神曲・熱量高)"
        elif row['engagement_rate'] >= 1.5:
            rank = " 良好なエンゲージメント"
        else:
            rank = "👀 一般ライト層中心 (再生数先行型)"
            
        st.write(f"**{row['short_title']}**")
        st.caption(f"ファンダム熱量: **{rank}**")
        st.write(f"・高評価数: `{row['likes']:,} 件` (`{row['like_rate']}%`)")
        st.write(f"・コメント数: `{row['comments']:,} 件` (`{row['comment_rate']}%`)")
        st.divider()
# ==========================================
# 5. AI自動診断 & PDF・印刷用レポート出力機能（完全ガード版）
# ==========================================
st.subheader("🤖 AI競合診断 ＆ PDFレポート自動出力")

# Session State でAI生成レポートを画面内に保持（他の操作をしても消えない）
if "ai_report_text" not in st.session_state:
    st.session_state.ai_report_text = ""

if GEMINI_API_KEY:
    col_ai1, col_ai2 = st.columns([1, 3])
    with col_ai1:
        if st.button("✨ Gemini AI で分析レポート生成", use_container_width=True):
            with st.spinner("Gemini APIでデータ分析中...（数秒かかります）"):
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=GEMINI_API_KEY)
                    model = genai.GenerativeModel("gemini-1.5-flash") # 既存の指定モデルがある場合はそれに合わせる
                    
                    prompt = f"""
あなたはエンタメ業界専門のデータアナリストです。
以下の競合MVパフォーマンスデータを分析し、マネジメント層向けに簡潔で実践的なインサイトレポートを作成してください。

【分析データ】
{df_summary[['full_title', 'views', 'lifetime_vph', 'current_vph', 'momentum_ratio']].to_string()}

【レポート構成案】
1. **全体サマリー**: 現在最も勢いのある動画と注意すべき傾向
2. **バズ勢い分析**: 通算平均に対して直近速度が急上昇/減速している理由考察
3. **自社へのアドバイス**: 次回リリース時に真似すべき/避けるべきポイント

専門用語は噛み砕き、箇条書きで分かりやすく出力してください。
"""
                    response = model.generate_content(prompt)
                    # 結果を Session State に保存
                    st.session_state.ai_report_text = response.text
                    st.success("✅ レポートの生成が完了しました！")
                    
                except Exception as e:
                    error_msg = str(e)
                    # 429エラー（制限超過）の場合の専用メッセージ
                    if "429" in error_msg or "Quota" in error_msg:
                        st.error("⚠️ AI APIの無料枠（短時間の回数制限）に達しました。約1分間待ってから、もう一度ボタンを押してください。")
                    else:
                        st.error(f"⚠️ AIの実行中にエラーが発生しました: {error_msg}")

    # AIレポートが生成されていれば表示
    if st.session_state.ai_report_text:
        st.markdown(st.session_state.ai_report_text)
else:
    st.info("💡 `GEMINI_API_KEY` を Streamlit Secrets に設定すると、AI自動診断機能が有効化されます。")

# --- 以降のHTML/PDFダウンロード機能のコードはそのまま残す ---

# --- レポート出力（HTML/PDF印刷対応）機能 ---
st.divider()
st.markdown(" **分析結果のエグゼクティブ・レポート出力**")

# HTMLレポートの動的生成
report_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>競合VPH & バズ解析レポート</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 30px; color: #333; }}
        h1 {{ color: #FF4B4B; border-bottom: 2px solid #FF4B4B; padding-bottom: 8px; }}
        h2 {{ color: #1f77b4; margin-top: 25px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
        th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <h1> 競合MVバズ解析 ＆ 伸び推移レポート</h1>
    <p>出力日時: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
    
    <h2>1. 比較動画データサマリー</h2>
    <table>
        <tr>
            <th>動画タイトル</th>
            <th>総再生数</th>
            <th>通算ヒットペース(回/時)</th>
            <th>直近速度(回/時)</th>
            <th>バズ加速率</th>
            <th>公開日時(JST)</th>
        </tr>
"""

for _, r in df_summary.iterrows():
    report_html += f"""
        <tr>
            <td>{r['full_title']}</td>
            <td>{r['views']:,} 回</td>
            <td>{r['lifetime_vph']:,}</td>
            <td>{r['current_vph']:,}</td>
            <td>{r['momentum_ratio']}倍</td>
            <td>{r['published_at_jst'].strftime('%Y-%m-%d %H:%M')} ({r['pub_day_jp']})</td>
        </tr>
"""

report_html += f"""
    </table>
    
    <h2>2. Gemini AI 競合分析インサイト</h2>
    <div>
        <pre style="white-space: pre-wrap; font-family: inherit; background: #f8f9fa; padding: 15px; border-radius: 5px;">
{st.session_state.ai_report_text if st.session_state.ai_report_text else "（AIレポート未生成です）"}
        </pre>
    </div>
</body>
</html>
"""

col_pdf, col_txt = st.columns(2)
with col_pdf:
    st.download_button(
        label=" 分析レポート（PDF/印刷用HTML）をダウンロード",
        data=report_html,
        file_name=f"VPH_Analytics_Report_{datetime.now().strftime('%Y%m%d')}.html",
        mime="text/html"
    )

with col_txt:
    st.download_button(
        label=" AIレポート（テキスト版）をダウンロード",
        data=st.session_state.ai_report_text if st.session_state.ai_report_text else "AIレポート未生成",
        file_name=f"AI_Report_{datetime.now().strftime('%Y%m%d')}.txt",
        mime="text/plain"
    )
