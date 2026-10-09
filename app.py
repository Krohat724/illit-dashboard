import os
import requests
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime, timezone
import google.generativeai as genai

# ==========================================
# 0. ページ基本設定 & カスタムCSS
# ==========================================
st.set_page_config(
    page_title=" YouTube競合バズ解析ダッシュボード",
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

# 動画ID抽出ユーティリティ
def extract_video_id(url):
    url = url.strip()
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    elif "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    elif len(url) == 11:
        return url
    return None

# ★【完全修復】APIキー制限やキャッシュバグを回避し、oEmbedから100%タイトルを回収する関数
def get_real_title(v_id, db_title, api_key):
    # 1. DB内のタイトルが正常に存在する場合はそれを使用
    if not pd.isna(db_title) and str(db_title).strip() not in ['None', 'nan', 'Unknown', '']:
        return str(db_title).strip()
    
    # 2. YouTube Data API キーで取得試行
    if api_key:
        try:
            yt_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={v_id}&key={api_key}"
            res = requests.get(yt_url, timeout=3).json()
            items = res.get("items", [])
            if items:
                t = items[0].get("snippet", {}).get("title")
                if t and str(t).strip() not in ['None', 'nan', 'Unknown', '']:
                    return t
        except Exception:
            pass
            
    # 3. 【APIキー不要の裏ワザ】YouTube oEmbed API からタイトルを100%確定取得
    try:
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={v_id}&format=json"
        res = requests.get(oembed_url, timeout=3).json()
        t = res.get("title")
        if t:
            return t
    except Exception:
        pass

    return "タイトル取得失敗"

import re

# 動画タイトルを「曲名 / アーティスト名」にスマート整形する関数
def clean_title(title, max_len=22):
    if not title or title in ["Unknown", "タイトル取得失敗"]:
        return "Unknown"
    
    raw = str(title).strip()
    
    # 1. 邪魔な [MV], 【MV】, [Official Video], (MV full) などのブラケット装飾を削除
    raw = re.sub(r'[\[【\(](?:MV|Official|PV|Full|Music Video|Performance).*?[\]】\)]', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'Official\s*(?:Music\s*)?Video', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'MUSIC\s*VIDEO', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'^[\[【\(]\s*[\]】\)]', '', raw).strip()
    
    # 2. アーティスト名と曲名を分離抽出
    artist, song = "", ""
    
    # パターンA: アーティスト名「曲名」または アーティスト名『曲名』
    m_quote = re.search(r'^(.*?)\s*[「『\'"](.*?)[」』\'"]', raw)
    if m_quote:
        artist = m_quote.group(1).strip()
        song = m_quote.group(2).strip()
    # パターンB: アーティスト名 / 曲名 または 曲名 / アーティスト名
    elif "/" in raw or "／" in raw:
        parts = re.split(r'[/／]', raw, maxsplit=1)
        p1, p2 = parts[0].strip(), parts[1].strip()
        if "「" in p2 or "『" in p2 or "'" in p2 or "」" in p2:
            artist, song = p1, p2
        else:
            song, artist = p1, p2
    else:
        m_single = re.search(r'[「『\'"](.*?)[」』\'"]', raw)
        if m_single:
            song = m_single.group(1).strip()
            artist = raw.replace(m_single.group(0), '').strip()
        else:
            song = raw
            artist = ""
            
    # アーティスト名のサブカッコ（韓国語表記など）を整理
    artist = re.sub(r'\(.*?\)', '', artist).strip()
    artist = re.sub(r'\[.*?\]', '', artist).strip()
    artist = re.sub(r'【.*?】', '', artist).strip()
    
    # 3. 「曲名 / アーティスト名」のフォーマットに結合
    if song and artist:
        formatted = f"{song} / {artist}"
    elif song:
        formatted = song
    else:
        formatted = raw
        
    formatted = re.sub(r'\s+', ' ', formatted).strip()
    
    if len(formatted) > max_len:
        return formatted[:max_len] + "…"
    return formatted
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

 # Supabaseから全データ読み込み
@st.cache_data(ttl=60)
def load_supabase_data():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return pd.DataFrame()
    try:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/multi_video_stats?select=*"
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            return pd.DataFrame(res.json())
    except Exception:
        pass
    return pd.DataFrame()

# ★ 時間経過に合わせてSupabaseへ最新データを自動スナップショット保存する関数
def auto_save_snapshot_if_needed(video_ids, live_stats, df_all, api_key):
    if not SUPABASE_URL or not SUPABASE_KEY or not video_ids:
        return
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    now_iso = datetime.now(timezone.utc).isoformat()
    
    for v_id in video_ids:
        df_v = df_all[df_all['video_id'] == v_id] if (not df_all.empty and 'video_id' in df_all.columns) else pd.DataFrame()
            
        should_insert = False
        if df_v.empty:
            should_insert = True
        else:
            df_v_ts = pd.to_datetime(df_v['timestamp'], utc=True)
            last_time = df_v_ts.max()
            minutes_since_last = (datetime.now(timezone.utc) - last_time).total_seconds() / 60
            if minutes_since_last >= 10:
                should_insert = True
                
        if should_insert:
            ls = live_stats.get(v_id)
            if not ls and api_key:
                ls_dict = fetch_live_video_stats([v_id], api_key)
                ls = ls_dict.get(v_id)
            
            if ls:
                payload = {
                    "video_id": v_id,
                    "title": ls.get("title", "Unknown"),
                    "views": ls.get("views", 0),
                    "likes": ls.get("likes", 0),
                    "comments": ls.get("comments", 0),
                    "published_at": ls.get("published_at"),
                    "timestamp": now_iso
                }
                try:
                    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/multi_video_stats"
                    requests.post(url, headers=headers, json=payload, timeout=3)
                except Exception:
                    pass

# --- メインデータ読み込み部分 ---
# ※ video_ids や YOUTUBE_API_KEY が定義されていることを確認した位置で実行
if 'video_ids' in locals() and 'YOUTUBE_API_KEY' in locals() and video_ids:
    live_stats = fetch_live_video_stats(video_ids, YOUTUBE_API_KEY)
else:
    live_stats = {}

df_all = load_supabase_data()

# アプリ起動時に最新スナップショットをSupabaseへ自動記録
if 'video_ids' in locals() and video_ids:
    auto_save_snapshot_if_needed(video_ids, live_stats, df_all, YOUTUBE_API_KEY if 'YOUTUBE_API_KEY' in locals() else "")

# スナップショット反映のため最新データを再読み込み
df_all = load_supabase_data()
df_filtered = df_all[df_all['video_id'].isin(video_ids)].copy() if (not df_all.empty and 'video_ids' in locals()) else pd.DataFrame()
# ==========================================
# 2. サイドバー：入力 & 手動更新
# ==========================================
st.sidebar.title("🎯 競合トラッキング設定")

st.sidebar.markdown("監視したい競合MVのURLを入力してください**（最大15本・改行区切り）**")

if "saved_urls_text" not in st.session_state:
    st.session_state.saved_urls_text = ""

urls_text = st.sidebar.text_area(
    "YouTube URL 一括入力",
    value=st.session_state.saved_urls_text,
    height=180,
    placeholder="https://www.youtube.com/watch?v=...\nhttps://www.youtube.com/watch?v=...",
    key="url_text_area"
)

st.session_state.saved_urls_text = urls_text

# 1. URLから video_ids を抽出
raw_urls = [u.strip() for u in urls_text.split("\n") if u.strip()]
video_ids = []
for u in raw_urls[:15]:
    v_id = extract_video_id(u)
    if v_id and v_id not in video_ids:
        video_ids.append(v_id)

st.sidebar.caption(f"現在の比較対象: **{len(video_ids)}本** / 最大15本")

# ★ 更新＆記録ボタン（スコープ・インデント完全修正版）
if st.sidebar.button("🔄 最新データに更新 ＆ 記録", use_container_width=True):
    st.cache_data.clear()
    
    save_count = 0
    error_msg = ""
    
    if not video_ids:
        st.sidebar.warning("⚠️ URLが入力されていません。")
    elif not SUPABASE_URL or not SUPABASE_KEY:
        st.sidebar.error("❌ Supabaseの接続情報(Secrets)が設定されていません。")
    else:
        now_iso = datetime.now(timezone.utc).isoformat()
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        current_live_stats = fetch_live_video_stats(video_ids, YOUTUBE_API_KEY)
        
        for v_id in video_ids:
            ls = current_live_stats.get(v_id, {})
            if ls:
                payload = {
                    "video_id": v_id,
                    "title": ls.get("title", "Unknown"),
                    "views": ls.get("views", 0),
                    "likes": ls.get("likes", 0),
                    "comments": ls.get("comments", 0),
                    "published_at": ls.get("published_at"),
                    "timestamp": now_iso
                }
                try:
                    res = requests.post(
                        f"{SUPABASE_URL.rstrip('/')}/rest/v1/multi_video_stats", 
                        headers=headers, 
                        json=payload, 
                        timeout=5
                    )
                    if res.status_code in [200, 201]:
                        save_count += 1
                    else:
                        error_msg = f"HTTP {res.status_code}: {res.text}"
                except Exception as e:
                    error_msg = str(e)
        
        if error_msg:
            st.sidebar.error(f"❌ 保存エラー発生:\n{error_msg}")
        elif save_count > 0:
            st.sidebar.success(f"✅ {save_count}件のスナップショットを記録しました！")
            import time
            time.sleep(1)
            st.rerun()

# 3. 追跡テーブルへの自動登録
if video_ids and SUPABASE_URL and SUPABASE_KEY:
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    for v_id in video_ids:
        try:
            track_url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/tracked_videos"
            track_headers = {**headers, "Prefer": "resolution=ignore-duplicates"}
            requests.post(track_url, headers=track_headers, json={"video_id": v_id}, timeout=3)
        except Exception:
            pass
# ==========================================
# 3. メイン画面ヘッダー
# ==========================================
st.title("YouTube競合バズ解析ダッシュボード")

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
# 4. 指標計算ロジック（実測差分VPH計算）
# ==========================================
summary_data = []
now_utc = datetime.now(timezone.utc)

for v_id in video_ids:
    df_v = df_filtered[df_filtered['video_id'] == v_id].copy() if not df_filtered.empty else pd.DataFrame()
    
    if df_v.empty:
        # DBにデータが一切ない場合 (初回)
        ls = live_stats.get(v_id, {})
        views = ls.get('views', 0)
        likes = ls.get('likes', 0)
        comments = ls.get('comments', 0)
        
        pub_at_raw = ls.get('published_at', now_utc.isoformat())
        pub_at = pd.to_datetime(pub_at_raw, utc=True)
        pub_at_jst = pub_at.tz_convert('Asia/Tokyo')
        
        full_title = get_real_title(v_id, ls.get('title'), YOUTUBE_API_KEY)
        short_title = clean_title(full_title)
        
        lifetime_hours = max((now_utc - pub_at).total_seconds() / 3600, 0.1)
        lifetime_vph = round(views / lifetime_hours, 1) if views > 0 else 0
        current_vph = lifetime_vph
        momentum_ratio = 1.0
        is_real_tracking = False
        tracking_time_str = "データなし"
        rec_count = 0
        
    else:
        # タイムスタンプを正しいdatetime型に変換して時系列ソート
        df_v['ts_dt'] = pd.to_datetime(df_v['timestamp'], utc=True)
        df_v = df_v.sort_values('ts_dt')
        rec_count = len(df_v)
        
        # 【青グラフ用】確実にDBの最新レコードから通算時速を計算（以前の安定コード）
        latest_row = df_v.iloc[-1]
        views = int(latest_row.get('views', latest_row.get('view_count', 0)))
        likes = int(latest_row.get('likes', latest_row.get('like_count', 0)))
        comments = int(latest_row.get('comments', latest_row.get('comment_count', 0)))
        
        pub_at_raw = latest_row.get('published_at')
        if pd.isna(pub_at_raw) or str(pub_at_raw) == 'None':
            snippets = fetch_video_snippets([v_id], YOUTUBE_API_KEY)
            pub_at_raw = snippets.get(v_id, {}).get('published_at', now_utc.isoformat())
            
        pub_at = pd.to_datetime(pub_at_raw, utc=True)
        pub_at_jst = pub_at.tz_convert('Asia/Tokyo')
        
        full_title = get_real_title(v_id, latest_row.get('title'), YOUTUBE_API_KEY)
        short_title = clean_title(full_title)
        
        lifetime_hours = max((now_utc - pub_at).total_seconds() / 3600, 0.1)
        lifetime_vph = round(views / lifetime_hours, 1)
        
        # 【オレンジグラフ用】直近勢い（現在速度）の計算
        if len(df_v) >= 2:
            #時間順に並び替え
            df_v['ts_dt'] = pd.to_datetime(df_v['timestamp'], utc=True)
            df_v = df_v.sort_values('ts_dt')

            latest_row = df_v.iloc[-1]
            
            # 過去データを探す（最新から「約3分以上前」の直近データ）
            ref_row = None
            for i in range(len(df_v)-2, -1, -1): 
                candidate = df_v.iloc[i]
                diff_sec = (latest_row['ts_dt'] - candidate['ts_dt']).total_seconds()
                if diff_sec >= 180: # 3分（180秒）以上前のデータを探す
                    ref_row = candidate
                    break
            
            # 3分以上空いていなければ、1つ前のデータを強制採用
            if ref_row is None:
                ref_row = df_v.iloc[-2]

            # 再生数と経過時間の差分から時速を計算
            tracking_hours = (latest_row['ts_dt'] - ref_row['ts_dt']).total_seconds() / 3600
            ref_views = int(ref_row.get('views', ref_row.get('view_count', 0)))
            views_diff = max(0, views - ref_views)
            
            if tracking_hours > 0.01: # 少しでも時間差があれば計算
                current_vph = round(views_diff / tracking_hours, 1)
                momentum_ratio = round(current_vph / lifetime_vph, 2) if lifetime_vph > 0 else 1.0
                is_real_tracking = True
                
                mins = round(tracking_hours * 60)
                if mins < 60:
                    tracking_time_str = f"直近 {max(mins, 1)} 分間の実測"
                else:
                    tracking_time_str = f"直近 {round(tracking_hours, 1)} 時間の実測"
            else:
                current_vph = lifetime_vph
                momentum_ratio = 1.0
                is_real_tracking = False
                tracking_time_str = "時間差不足のため通算と同値"
        else:
            current_vph = lifetime_vph
            momentum_ratio = 1.0
            is_real_tracking = False
            tracking_time_str = "蓄積データ1件のため通算と同値"

    summary_data.append({
        "video_id": v_id,
        "full_title": full_title,
        "short_title": short_title,
        "views": views,
        "likes": likes,
        "comments": comments,
        "published_at_jst": pub_at_jst,
        "lifetime_hours": round(lifetime_hours, 1),
        "lifetime_vph": lifetime_vph,
        "current_vph": current_vph,
        "momentum_ratio": momentum_ratio,
        "is_real_tracking": is_real_tracking,
        "tracking_time_str": tracking_time_str,
        "rec_count": len(df_v),
        "pub_day": pub_at_jst.strftime('%A'),
        "pub_hour": pub_at_jst.hour
    })

if summary_data:
    df_summary = pd.DataFrame(summary_data)
else:
    st.warning("⚠️ 有効なYouTube URLを入力してください。")
    st.stop()

# ==========================================
# 機能 1: 📊 2軸スピード比較（通算平均伸び × 直近のバズ勢い）
# ==========================================
st.subheader("1. 📊 ヒットスピード比較（通算平均伸び × 直近のバズ勢い）")
st.info("💡 時間を置いてサイドバーの「最新データに更新 ＆ 記録」を押すと、差分から計算された『直近のバズ勢い（オレンジ）』が最新時速に切り替わります！")

col1, col2 = st.columns([2, 1])

with col1:
    fig_vph = go.Figure()

    # 1. 通算ヒットペース (青色の棒: 見慣れた元のグラフ)
    fig_vph.add_trace(go.Bar(
        x=df_summary['short_title'],
        y=df_summary['lifetime_vph'],
        name='通算ヒットペース (平均時速)',
        marker_color='#1f77b4',
        text=[f"{v:,.0f}" for v in df_summary['lifetime_vph']],
        textposition='auto',
        hovertext=df_summary['full_title']
    ))

    # 2. 現在のバズ勢い (オレンジ色の棒: こちらも元のデザイン)
    fig_vph.add_trace(go.Bar(
        x=df_summary['short_title'],
        y=df_summary['current_vph'],
        name='現在のバズ勢い (直近時速)',
        marker_color='#ff7f0e',
        text=[f"{v:,.0f}" for v in df_summary['current_vph']],
        textposition='auto',
        hovertext=df_summary['full_title']
    ))

    fig_vph.update_layout(
        barmode='group',
        title="動画別 再生速度（VPH）比較",
        xaxis_title="動画タイトル (曲名 / アーティスト)",
        yaxis_title="再生増加数 (回 / 時間)",
        legend=dict(orientation="h", y=1.15)
    )
    st.plotly_chart(fig_vph, use_container_width=True)

with col2:
    st.markdown("##### 🚀 スピード & 勢い判定")
    for _, row in df_summary.iterrows():
        l_vph = row['lifetime_vph']
        ratio = row['momentum_ratio']
        
        if l_vph >= 10000:
            speed_rank = "🔥 Sランク (1万+ VPH)"
        elif l_vph >= 3000:
            speed_rank = "✨ Aランク (3,000+ VPH)"
        elif l_vph >= 1000:
            speed_rank = "👍 Bランク (1,000+ VPH)"
        else:
            speed_rank = "👀 Cランク (1,000未満)"

        st.write(f"**{row['short_title']}**")
        st.caption(f"📦 DB蓄積データ: **{row['rec_count']}件**")
        st.write(f"・通算規模: **{speed_rank}**")
        
        if row['is_real_tracking']:
            status_str = "⚡ 加速中" if ratio > 1.05 else ("📉 減速中" if ratio < 0.95 else "➡️ 安定維持")
            st.markdown(f"・直近勢い: **{ratio}倍 ({status_str})** <span style='font-size:0.8em;color:gray;'>[{row['tracking_time_str']}]</span>", unsafe_allow_html=True)
        else:
            st.markdown(f"・直近勢い: <span style='color:gray;'>⏳ 蓄積中 ({row['tracking_time_str']})</span>", unsafe_allow_html=True)
            
        st.write(f"・直近時速: `{row['current_vph']:,.1f} 回/時`")
        st.write(f"・通算時速: `{l_vph:,.1f} 回/時`")
        st.divider()
    

# ==========================================
# 機能 2: 競合新曲 Launch Tracker（初速レーダー）
# =========================================
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
# 機能 3: 投稿日時 × バズ速度マトリクス（勝ちパターン分析）
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


from plotly.subplots import make_subplots

# ==========================================
# 機能 4: ファンダム熱量スコア（分離グラフ & 相対ランク判定）
# ==========================================
st.subheader("4.  ファンダム熱量スコア")
st.markdown("""
再生数に対してファンがどれだけ積極的に高評価・コメントを残しているかを測定します。
高評価とコメントの比率を個別に分析し、比較対象の中での相対的な熱量ランクを算出します。
""")

# 1,000再生あたりの高評価数・コメント数計算
df_summary['likes_per_1k'] = (df_summary['likes'] / df_summary['views'] * 1000).round(1)
df_summary['comments_per_1k'] = (df_summary['comments'] / df_summary['views'] * 1000).round(1)
df_summary['total_action_per_1k'] = (df_summary['likes_per_1k'] + df_summary['comments_per_1k']).round(1)

col_f1, col_f2 = st.columns([2, 1])

with col_f1:
    # 左右2軸で「高評価」と「コメント」を並列（group）表示
    fig_fandom = make_subplots(specs=[[{"secondary_y": True}]])

    fig_fandom.add_trace(
        go.Bar(
            x=df_summary['short_title'],
            y=df_summary['likes_per_1k'],
            name='高評価数 (1k再生あたり)',
            marker_color='#2ca02c',
            offsetgroup=1
        ),
        secondary_y=False
    )

    fig_fandom.add_trace(
        go.Bar(
            x=df_summary['short_title'],
            y=df_summary['comments_per_1k'],
            name='コメント数 (1k再生あたり)',
            marker_color='#d62728',
            offsetgroup=2
        ),
        secondary_y=True
    )

    fig_fandom.update_layout(
        barmode='group',
        title="1,000回再生あたりの 高評価数 vs コメント数 分離比較",
        xaxis_title="動画タイトル (曲名 / アーティスト)",
        legend=dict(orientation="h", y=1.15)
    )

    fig_fandom.update_yaxes(title_text="高評価数 (回 / 1k再生)", secondary_y=False)
    fig_fandom.update_yaxes(title_text="コメント数 (回 / 1k再生)", secondary_y=True)

    st.plotly_chart(fig_fandom, use_container_width=True)

with col_f2:
    st.markdown("#####  相対ファンダム熱量ランク")
    
    # 比較対象の中での平均値・最高値を基準にした相対判定
    avg_action = df_summary['total_action_per_1k'].mean()
    max_action = df_summary['total_action_per_1k'].max()
    
    df_fandom_sorted = df_summary.sort_values('total_action_per_1k', ascending=False)
    
    for rank, (_, row) in enumerate(df_fandom_sorted.iterrows(), 1):
        tot = row['total_action_per_1k']
        
        # 比較対象群の中での相対ランク判定
        if tot >= max_action * 0.9 and tot > avg_action:
            rank_badge = " Sランク (群を抜く熱狂度)"
        elif tot >= avg_action * 1.05:
            rank_badge = " Aランク (平均以上・高熱量)"
        elif tot >= avg_action * 0.85:
            rank_badge = " Bランク (平均的)"
        else:
            rank_badge = " Cランク (ライト層多め)"
            
        st.write(f"**#{rank} {row['short_title']}**")
        st.write(f"・熱量判定: **{rank_badge}**")
        st.write(f"・1,000再生あたり: **`{tot} 回`** リアクション")
        st.caption(f" (高評価: {row['likes_per_1k']}回 | 💬コメント: {row['comments_per_1k']}回)")
        st.divider()

# ==========================================
# 5. AI自動診断 & PDF・印刷用レポート出力機能（AI結果固定版）
# ==========================================
st.subheader(" AI競合診断 ＆ PDFレポート自動出力")

# Session State でAI生成レポートを画面内に保持（他の操作をしても消えない）
if "ai_report_text" not in st.session_state:
    st.session_state.ai_report_text = ""

if GEMINI_API_KEY:
    col_ai1, col_ai2 = st.columns([1, 3])
    with col_ai1:
        if st.button(" Gemini AI で分析レポート生成", use_container_width=True):
            with st.spinner("Gemini APIでデータ分析中..."):
                try:
                    genai.configure(api_key=GEMINI_API_KEY)
                    model = genai.GenerativeModel("gemini-3.8-flash")
                    
                    prompt = f"""
あなたはK-POP/J-POPエンタメ業界専門のデータアナリストです。
以下の競合MVパフォーマンスデータを分析し、芸能事務所のマネージャー向けに簡潔で実践的なインサイトレポートを作成してください。

【分析データ】
{df_summary[['full_title', 'views', 'lifetime_vph', 'current_vph', 'momentum_ratio', 'pub_day_jp', 'pub_hour']].to_string()}

【レポート構成案】
1. **全体サマリー**: 現在最も勢いのある動画と注意すべき傾向
2. **バズ勢い分析**: 通算平均に対して直近速度が急上昇/減速している動画の理由考察
3. **投稿戦略の勝ちパターン**: 投稿曜日・時間帯から見出せる競合のリリース戦略
4. **自社グループへのアドバイス**: 次回リリース時に真似すべき/避けるべきポイント

専門用語は噛み砕き、箇条書きで分かりやすく出力してください。
"""
                    response = model.generate_content(prompt)
                    # 結果を Session State に保存（画面リロードしても消えない）
                    st.session_state.ai_report_text = response.text
                except Exception as e:
                    st.error(f"Gemini API実行エラー: {e}")

    # AIレポートが生成されていれば表示
    if st.session_state.ai_report_text:
        st.markdown(st.session_state.ai_report_text)
else:
    st.info(" `GEMINI_API_KEY` を Streamlit Secrets に設定すると、AI自動診断機能が有効化されます。")

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
        label="AIレポート（テキスト版）をダウンロード",
        data=st.session_state.ai_report_text if st.session_state.ai_report_text else "AIレポート未生成",
        file_name=f"AI_Report_{datetime.now().strftime('%Y%m%d')}.txt",
        mime="text/plain"
    )
