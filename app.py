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
    page_title="競合VPH & Launch Tracker SaaS",
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
    "Content-Type": "application/json"
}

# 動画ID抽出ユーティリティ
def extract_video_id(url):
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    elif "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    elif len(url) == 11:
        return url
    return None

# YouTube APIから snippet (publishedAt等) を自動キャッシュ取得
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
                "published_at": snippet.get("publishedAt"),
                "channel_title": snippet.get("channelTitle", "Unknown")
            }
    except Exception:
        pass
    return info_map

# Supabaseにまだ保存されていない動画データをYouTube APIから直接ライブ取得する関数
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

# Supabaseから全蓄積データを取得
@st.cache_data(ttl=60)
def load_supabase_data():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return pd.DataFrame()
    try:
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/multi_video_stats?select=*"
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            df = pd.DataFrame(res.json())
            return df
    except Exception:
        pass
    return pd.DataFrame()

# ==========================================
# 2. サイドバー：比較対象の設定 & 自動登録
# ==========================================
st.sidebar.title(" 競合トラッキング設定")
st.sidebar.markdown("監視したい競合MVのURLを入力してください（最大5本）")

url_inputs = [
    st.sidebar.text_input(f"動画URL #{i+1}", key=f"url_{i}") 
    for i in range(5)
]

active_urls = [u for u in url_inputs if u.strip()]
video_ids = [extract_video_id(u) for u in active_urls if extract_video_id(u)]

# 入力された動画IDを Supabase の tracked_videos へ自動登録
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
st.title(" K-POP/J-POP 競合VPH & Launch Analytics")
st.caption("リアルタイムモメンタム × 投稿日時勝ちパターン分析 SaaS")

df_all = load_supabase_data()

if len(video_ids) == 0:
    st.info("👈 サイドバーに競合動画のYouTube URLを入力してください。分析を開始します。")
    st.stop()

# 選択された動画データのみフィルター
df_filtered = df_all[df_all['video_id'].isin(video_ids)].copy() if not df_all.empty else pd.DataFrame()

# 日時型変換
if not df_filtered.empty:
    df_filtered['timestamp'] = pd.to_datetime(df_filtered['timestamp'], utc=True)
    if 'published_at' in df_filtered.columns:
        df_filtered['published_at'] = pd.to_datetime(df_filtered['published_at'], utc=True)

now_utc = datetime.now(timezone.utc)

# ==========================================
# 4. 指標計算ロジック（Lifetime VPH & モメンタム）
# ==========================================
summary_data = []

# Supabaseにデータがない新規動画を特定してリアルタイム取得
missing_vids = [v for v in video_ids if df_filtered.empty or df_filtered[df_filtered['video_id'] == v].empty]
live_stats = fetch_live_video_stats(missing_vids, YOUTUBE_API_KEY) if missing_vids else {}

for v_id in video_ids:
    df_v = df_filtered[df_filtered['video_id'] == v_id].sort_values('timestamp') if not df_filtered.empty else pd.DataFrame()
    
    # 蓄積データがない新規URLの場合、ライブ取得したデータで生成
    if df_v.empty:
        if v_id in live_stats:
            ls = live_stats[v_id]
            title = ls['title']
            views = ls['views']
            pub_at = pd.to_datetime(ls['published_at'], utc=True)
            pub_at_jst = pub_at.tz_convert('Asia/Tokyo')
            
            lifetime_hours = max((now_utc - pub_at).total_seconds() / 3600, 0.1)
            lifetime_vph = round(views / lifetime_hours, 1)
            current_vph = lifetime_vph  # 初回表示は通算VPHを適用
            momentum_ratio = 1.0
            
            summary_data.append({
                "video_id": v_id,
                "title": title,
                "views": views,
                "published_at_jst": pub_at_jst,
                "lifetime_hours": round(lifetime_hours, 1),
                "lifetime_vph": lifetime_vph,
                "current_vph": current_vph,
                "momentum_ratio": momentum_ratio,
                "pub_day": pub_at_jst.strftime('%A'),
                "pub_hour": pub_at_jst.hour
            })
        continue

    # 蓄積データが存在する場合
    latest_row = df_v.iloc[-1]
    first_row = df_v.iloc[0]
    
    title = latest_row.get('title', 'Unknown')
    views = int(latest_row.get('views', latest_row.get('view_count', 0)))
    
    pub_at_raw = latest_row.get('published_at')
    if pd.isna(pub_at_raw) or str(pub_at_raw) == 'None':
        snippets = fetch_video_snippets([v_id], YOUTUBE_API_KEY)
        pub_at_raw = snippets.get(v_id, {}).get('published_at', now_utc.isoformat())
        
    pub_at = pd.to_datetime(pub_at_raw, utc=True)
    pub_at_jst = pub_at.tz_convert('Asia/Tokyo')
    
    # 公開からの経過時間(h)
    lifetime_hours = max((now_utc - pub_at).total_seconds() / 3600, 0.1)
    
    # ① Lifetime VPH
    lifetime_vph = round(views / lifetime_hours, 1)
    
    # ② 現在モメンタム VPH
    tracking_hours = (latest_row['timestamp'] - first_row['timestamp']).total_seconds() / 3600
    if tracking_hours > 0.1:
        views_diff = views - int(first_row.get('views', first_row.get('view_count', 0)))
        current_vph = round(views_diff / tracking_hours, 1)
    else:
        current_vph = lifetime_vph
        
    momentum_ratio = round(current_vph / lifetime_vph, 2) if lifetime_vph > 0 else 1.0
    
    summary_data.append({
        "video_id": v_id,
        "title": title,
        "views": views,
        "published_at_jst": pub_at_jst,
        "lifetime_hours": round(lifetime_hours, 1),
        "lifetime_vph": lifetime_vph,
        "current_vph": current_vph,
        "momentum_ratio": momentum_ratio,
        "pub_day": pub_at_jst.strftime('%A'),
        "pub_hour": pub_at_jst.hour
    })

# データフレーム化（空ガード付き）
if summary_data:
    df_summary = pd.DataFrame(summary_data)
else:
    st.warning(" データの取得に失敗したか、有効なYouTube URLではありません。")
    st.stop()

# ==========================================
# 機能 1:  2軸スピード比較（Lifetime VPH vs 現在モメンタム）
# ==========================================
st.subheader("1.  2軸スピード比較（Lifetime VPH × 現在モメンタム）")
st.markdown("""
* **Lifetime VPH**: 公開から現在までの平均時速（過去動画同士の公平な速度基準）
* **現在モメンタム VPH**: ツール登録後のリアルタイムの勢い（今バズっているか）
""")

col1, col2 = st.columns([2, 1])

with col1:
    fig_vph = go.Figure()
    fig_vph.add_trace(go.Bar(
        x=df_summary['title'],
        y=df_summary['lifetime_vph'],
        name='Lifetime VPH (平均時速)',
        marker_color='#1f77b4'
    ))
    fig_vph.add_trace(go.Bar(
        x=df_summary['title'],
        y=df_summary['current_vph'],
        name='現在モメンタム VPH (直近時速)',
        marker_color='#ff7f0e'
    ))
    fig_vph.update_layout(
        barmode='group',
        title="動画別 VPH 速度比較",
        xaxis_title="動画タイトル",
        yaxis_title="VPH (再生増加数 / 時間)",
        legend=dict(orientation="h", y=1.1)
    )
    st.plotly_chart(fig_vph, use_container_width=True)

with col2:
    st.markdown("#####  モメンタム判定")
    for _, row in df_summary.iterrows():
        status = " 急加速中" if row['momentum_ratio'] > 1.2 else ("📉 減速傾向" if row['momentum_ratio'] < 0.8 else "➡️ 安定維持")
        st.write(f"**{row['title'][:15]}...**")
        st.caption(f"現在の勢い: **{row['momentum_ratio']}倍** ({status})")
        st.write(f"・現在時速: `{row['current_vph']:,} VPH`")
        st.write(f"・通算時速: `{row['lifetime_vph']:,} VPH`")
        st.divider()

# ==========================================
# 機能 2:  競合新曲「事前登録・自動監視（Launch Tracker）」
# ==========================================
st.subheader("2.  競合新曲 Launch Tracker（初速レーダー）")
st.caption("公開直後（72時間以内）の新曲MVを自動検知し、初期ロケットスタート速度を追跡")

df_new_releases = df_summary[df_summary['lifetime_hours'] <= 72]

if not df_new_releases.empty:
    st.success(f" 追跡中の対象に **{len(df_new_releases)}本** の新曲（公開72時間以内）を検知しました！")
    cols = st.columns(len(df_new_releases))
    for idx, (_, row) in enumerate(df_new_releases.iterrows()):
        with cols[idx % len(cols)]:
            st.metric(
                label=f" {row['title'][:18]}...",
                value=f"{row['views']:,} 回",
                delta=f"初速 {row['lifetime_vph']:,} VPH"
            )
            st.caption(f" 公開: {row['published_at_jst'].strftime('%m/%d %H:%M')} (経過: {row['lifetime_hours']}h)")
else:
    st.info(" 現在、選択されたURLの中に公開72時間以内の『新曲』はありません。これから公開される新曲MVのURLを登録しておくと、公開0分目からの完全な初速VPHが蓄積されます。")

# ==========================================
# 機能 3:  投稿日時 × バズ速度マトリクス（Publishing Matrix）
# ==========================================
st.subheader("3.  投稿日時 × バズ速度（JST 勝ちパターン分析）")
st.markdown("競合動画の `公開曜日` と `公開時間帯（日本時間 JST）` を分析し、**どのタイミングで出された動画が最も高い Lifetime VPH を記録しているか** を可視化します。")

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
        labels=dict(x="公開時間帯 (時)", y="公開曜日", color="平均 Lifetime VPH"),
        x=[f"{h}時" for h in matrix_df.columns],
        title="投稿タイミング別 平均 Lifetime VPH ヒートマップ",
        color_continuous_scale="Reds"
    )
    st.plotly_chart(fig_matrix, use_container_width=True)
    
    best_row = df_summary.loc[df_summary['lifetime_vph'].idxmax()]
    st.success(f" **競合の最高ヒットタイミング分析結果**\n\n"
               f"最も高い初速・バズ速度（`{best_row['lifetime_vph']:,} VPH`）を記録しているのは **『{best_row['pub_day_jp']}曜日の {best_row['pub_hour']}時』** に公開された動画（`{best_row['title']}`）です！")

# ==========================================
# 5. Gemini API による自動AI競合レポート生成
# ==========================================
st.subheader("Gemini AI による競合モメンタム診断レポート")

if GEMINI_API_KEY:
    if st.button("AI解説レポートを生成する"):
        with st.spinner("Gemini APIでデータ分析中..."):
            try:
                genai.configure(api_key=GEMINI_API_KEY)
                model = genai.GenerativeModel("gemini-3.8-flash")
                
                prompt = f"""
あなたはK-POP/J-POPエンタメ業界専門のデータアナリストです。
以下の競合MVパフォーマンスデータを分析し、芸能事務所のマネージャー向けに簡潔で実践的なインサイトレポートを作成してください。

【分析データ】
{df_summary[['title', 'views', 'lifetime_vph', 'current_vph', 'momentum_ratio', 'pub_day_jp', 'pub_hour']].to_string()}

【レポート構成案】
1. **全体サマリー**: 現在最も勢いのある動画と注意すべき傾向
2. **モメンタム分析**: 通算速度(Lifetime VPH)に対して直近速度(現在VPH)が急上昇/減速している動画の理由考察
3. **投稿戦略の勝ちパターン**: 投稿曜日・時間帯から見出せる競合のリリース戦略
4. **自社グループへのアドバイス**: 次回リリース時に真似すべき/避けるべきポイント

専門用語は噛み砕き、箇条書きで分かりやすく出力してください。
"""
                response = model.generate_content(prompt)
                st.markdown(response.text)
            except Exception as e:
                st.error(f"Gemini API実行エラー: {e}")
else:
    st.info(" `GEMINI_API_KEY` を Streamlit Secrets に設定すると、AI自動診断レポート機能が有効化されます。")
