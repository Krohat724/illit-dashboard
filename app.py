import streamlit as st
import requests
import pandas as pd
import altair as alt
import re
import io
from datetime import datetime
from typing import Optional, List
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# ReportLab (PDF生成用)
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# --- 1. 初期設定 & APIクライアント ---
st.set_page_config(page_title="K-POP/J-POP 競合分析SaaS", layout="wide")

API_KEY = st.secrets["YOUTUBE_API_KEY"]
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

# Gemini Clientの初期化
client = genai.Client(api_key=GEMINI_API_KEY)

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# --- Pydantic定義（機能4: AIコメント解析用） ---
class CommentAnalysisResponse(BaseModel):
    praise_points: List[str] = Field(description="ファンが最も褒めているポイント3選")
    overseas_reaction: str = Field(description="海外ファンからの反応の割合と概要")
    negative_points: str = Field(description="ネガティブ・違和感のあるコメントの有無と内容")

# --- ユーティリティ関数 ---
def extract_video_id(url):
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
    return match.group(1) if match else None

def fetch_supabase_data():
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/multi_video_stats?select=*"
    res = requests.get(url, headers=headers)
    if res.status_code == 200 and res.json():
        df = pd.DataFrame(res.json())
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    return pd.DataFrame()

# ==========================================
# メインUI構成
# ==========================================
st.title("🔥 K-POP / J-POP 競合リアルタイム分析ダッシュボード")

# データベースから全履歴を取得
df_all = fetch_supabase_data()

# --- サイドバー：比較対象動画の入力（3〜5本） ---
st.sidebar.header("🎯 比較対象動画の設定 (3〜5本)")
url_inputs = [
    st.sidebar.text_input(f"動画 URL #{i+1}", key=f"url_{i}")
    for i in range(5)
]

active_urls = [u for u in url_inputs if u.strip()]
video_ids = [extract_video_id(u) for u in active_urls if extract_video_id(u)]

if len(video_ids) < 1:
    st.info("👈 左側のサイドバーに、比較したいYouTube動画のURLを少なくとも1本以上入力しろ。")
    st.stop()

# --- 比較動画データのYouTube API一括取得 ---
ids_str = ",".join(video_ids)
yt_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&id={ids_str}&key={API_KEY}"
yt_data = requests.get(yt_url).json().get("items", [])

if not yt_data:
    st.error("動画データの取得に失敗した。URLを確認しろ。")
    st.stop()

# ==========================================
# 機能 1: 公開後スピード比較（初速相対グラフ）
# ==========================================
st.header("1. 🚀 公開後スピード比較（初速相対グラフ）")

if not df_all.empty:
    df_filtered = df_all[df_all['video_id'].isin(video_ids)].copy()
    
    # published_at が存在するかチェック
    if 'published_at' in df_filtered.columns and not df_filtered['published_at'].isnull().all():
        # 日時型変換 (UTC統一)
        df_filtered['timestamp'] = pd.to_datetime(df_filtered['timestamp'], utc=True)
        df_filtered['published_at'] = pd.to_datetime(df_filtered['published_at'], utc=True)
        
        # 経過時間（Hours）の計算: (取得日時 - 公開日時) の秒数 ÷ 3600
        df_filtered['elapsed_hours'] = (df_filtered['timestamp'] - df_filtered['published_at']).dt.total_seconds() / 3600
        df_filtered['elapsed_days'] = (df_filtered['elapsed_hours'] / 24).round(1)
        
        # X軸の切り替えオプション
        unit = st.radio("X軸の単位を選択しろ", ["公開後の経過時間 (Hours)", "公開後の経過日数 (Days)"], horizontal=True)
        x_col = 'elapsed_hours' if "Hours" in unit else 'elapsed_days'
        x_label = '公開からの経過時間 (時間)' if "Hours" in unit else '公開からの経過日数 (日)'

        # Altairで公開後の経過時間X軸グラフを描画
        chart = alt.Chart(df_filtered).mark_line(point=True).encode(
            x=alt.X(f'{x_col}:Q', title=x_label),
            y=alt.Y('views:Q', title='再生回数', scale=alt.Scale(zero=True)),
            color=alt.Color('title:N', title='動画タイトル'),
            tooltip=['title', f'{x_col}:Q', 'views']
        ).properties(height=380).interactive()
        
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("💡 `published_at`（公開日時）の入ったデータがまだ蓄積されていない。`update_data.py` の次回実行を待つか、データを取得しろ。")
else:
    st.warning("蓄積データが存在しない。")

# ==========================================
# 機能 2 & 3: 熱意度指数 & 初速マトリクス
# ==========================================
col_left, col_right = st.columns(2)

metrics_list = []

for item in yt_data:
    v_id = item['id']
    title = item['snippet']['title']
    pub_at = pd.to_datetime(item['snippet']['publishedAt']).tz_convert('Asia/Tokyo')
    
    stats = item['statistics']
    views = int(stats.get('viewCount', 0))
    likes = int(stats.get('likeCount', 0))
    comments = int(stats.get('commentCount', 0))
    
    # 【機能2: ファンダム熱意度指数】
    er = ((likes + comments) / views * 100) if views > 0 else 0
    if er >= 8.0: rank = "S (熱狂的)"
    elif er >= 4.0: rank = "A (高熱量)"
    elif er >= 2.0: rank = "B (標準)"
    else: rank = "C (低迷)"
    
    # 【機能3: 投稿時間帯×初速VPH】
    day_hour = pub_at.strftime('%A (%H:00公開)')
    
    metrics_list.append({
        "video_id": v_id,
        "タイトル": title,
        "総再生数": views,
        "エンゲージメント率": f"{er:.2f}%",
        "熱量ランク": rank,
        "公開日時": day_hour,
        "likes": likes,
        "comments": comments
    })

df_metrics = pd.DataFrame(metrics_list)

with col_left:
    st.header("2. 🔥 ファンダム熱意度指数")
    st.dataframe(df_metrics[["タイトル", "総再生数", "エンゲージメント率", "熱量ランク"]], use_container_width=True)

with col_right:
    st.header("3. ⏰ 投稿時間帯・公開タイミング")
    st.dataframe(df_metrics[["タイトル", "公開日時"]], use_container_width=True)

st.divider()

# ==========================================
# 機能 4: Gemini AIコメント感情＆バズ要因サマリー
# ==========================================
st.header("4. 🤖 Gemini AIコメント感情 & バズ要因分析")

selected_video_title = st.selectbox("AI解析を行う動画を選択しろ", df_metrics["タイトル"].tolist())
selected_video_id = df_metrics[df_metrics["タイトル"] == selected_video_title]["video_id"].values[0]

if st.button("最新50件のコメントをGeminiで解析する"):
    with st.spinner("YouTubeコメントを取得し、Geminiで解析中..."):
        comment_url = f"https://www.googleapis.com/youtube/v3/commentThreads?part=snippet&videoId={selected_video_id}&maxResults=50&key={API_KEY}"
        c_res = requests.get(comment_url).json()
        
        comments_text = []
        if "items" in c_res:
            for c_item in c_res["items"]:
                text = c_item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
                comments_text.append(text)
        
        if comments_text:
            prompt = f"""
あなたはエンタメ市場のデータアナリストです。
以下のYouTube動画のコメント50件を分析し、ファンの反響ポイント、海外ファンの反応、ネガティブ要素を整理してください。

【コメント一覧】
""" + "\n".join(comments_text)

            # Gemini API呼び出し (エラー捕捉付き)
            try:
                response = client.models.generate_content(
                    model='gemini-3.8-flash',  # 最も安定している公式モデル
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=CommentAnalysisResponse,
                        temperature=0.2,
                    ),
                )
                
                # Pydanticモデルへパース
                ai_res = CommentAnalysisResponse.model_validate_json(response.text)
                
                st.session_state['ai_analysis'] = ai_res
                st.session_state['ai_target_title'] = selected_video_title
                
                st.success("Gemini解析完了！")
                st.subheader("👍 ファンが褒めているポイント")
                for pt in ai_res.praise_points:
                    st.write(f"- {pt}")
                    
                st.subheader("🌍 海外ファンの反応")
                st.write(ai_res.overseas_reaction)
                
                st.subheader("⚠️ 違和感・ネガティブ要素")
                st.write(ai_res.negative_points)

            except Exception as e:
                # クラッシュさせずに画面上に本当のエラーメッセージを表示する
                st.error(f"❌ Gemini API実行エラー: {e}")
        else:
            st.warning("コメントが取得できないか、オフになっています。")

# ==========================================
# 機能 5: ワンクリック「1P分析レポート（PDF）」出力
# ==========================================
st.header("5. 📄 エグゼクティブ向け 1PサマリーPDF出力")

def generate_pdf(df_m, ai_data, ai_title):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # ヘッダー
    p.setFont("Helvetica-Bold", 16)
    p.drawString(40, height - 50, "K-POP / J-POP Competitive Analysis Report")
    p.setFont("Helvetica", 10)
    p.drawString(40, height - 65, f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    p.line(40, height - 75, width - 40, height - 75)
    
    # 1. パフォーマンス指標
    y = height - 100
    p.setFont("Helvetica-Bold", 12)
    p.drawString(40, y, "1. Performance & Engagement Metrics")
    y -= 20
    
    p.setFont("Helvetica", 9)
    for _, row in df_m.iterrows():
        safe_title = row['タイトル'].encode('ascii', 'ignore').decode('ascii')
        if not safe_title: safe_title = f"Video ID: {row['video_id']}"
        
        line = f"- {safe_title[:30]}... | Views: {row['総再生数']} | ER: {row['エンゲージメント率']} | Rank: {row['熱量ランク']}"
        p.drawString(50, y, line)
        y -= 15
        
    # 2. AIコメント解析
    y -= 20
    p.setFont("Helvetica-Bold", 12)
    p.drawString(40, y, "2. Gemini AI Comment Sentiment Summary")
    y -= 20
    
    p.setFont("Helvetica", 9)
    if ai_data:
        p.drawString(50, y, f"Target: {ai_title[:40]}...")
        y -= 15
        p.drawString(50, y, f"Overseas Reaction: {ai_data.overseas_reaction[:60]}...")
        y -= 15
        p.drawString(50, y, f"Negative Signals: {ai_data.negative_points[:60]}...")
    else:
        p.drawString(50, y, "No AI Analysis performed yet.")
        
    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

if st.button("📄 1Pレポート（PDF）を発行・ダウンロード"):
    ai_data = st.session_state.get('ai_analysis', None)
    ai_title = st.session_state.get('ai_target_title', "")
    
    pdf_buffer = generate_pdf(df_metrics, ai_data, ai_title)
    
    st.download_button(
        label="📥 今すぐPDFをダウンロードしろ",
        data=pdf_buffer,
        file_name=f"KPOP_Analysis_Report_{datetime.now().strftime('%Y%m%d')}.pdf",
        mime="application/pdf"
    )
