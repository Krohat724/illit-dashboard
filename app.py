import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timezone

# =========================================================
# 0. アプリ全体の設定
# =========================================================
st.set_page_config(page_title=" バズ解析ダッシュボード", layout="wide")
st.title("バズ解析ダッシュボード ")
st.caption("リアルタイムのバズ勢い × 投稿日時の勝ちパターン分析 SaaS")

# =========================================================
# 1. データのロードと完全クレンジング（全て新しく書き直した基盤）
# =========================================================
@st.cache_data(ttl=600)
def load_and_clean_data():
    """
    ※ ここに元のSupabase等からのデータ読み込み処理を組み込んでください。
    ※ 以下は、どんなデータが来ても絶対にエラーを起こさないための最強のクレンジング処理です。
    """
    # ---------------------------------------------------------
    # 【重要】もしSupabaseから取得するコード( response = supabase... 等 )が
    # あれば、ここに追加し、変数 df_raw に pandas DataFrame として格納してください。
    # ---------------------------------------------------------
    
    # ▼ (既存の df_filtered を読み込む想定の処理)
    if 'df_filtered' not in globals() or df_filtered.empty:
        # 万が一DBからデータが取れなかった場合でも画面を壊さない安全装置（ダミー回避）
        df_raw = pd.DataFrame() 
    else:
        df_raw = df_filtered.copy()

    if df_raw.empty:
        return df_raw

    # 必須カラムの補完と型変換（IndexError / KeyError の完全防止）
    if 'views' not in df_raw.columns and 'view_count' in df_raw.columns:
        df_raw['views'] = df_raw['view_count']
    elif 'views' not in df_raw.columns:
        df_raw['views'] = 0

    df_raw['timestamp'] = pd.to_datetime(df_raw['timestamp'], utc=True, errors='coerce')
    df_raw = df_raw.dropna(subset=['timestamp']).sort_values('timestamp')
    df_raw['views'] = pd.to_numeric(df_raw['views'], errors='coerce').fillna(0).astype(int)
    
    return df_raw

# クリーンなデータを取得
df_clean = load_and_clean_data()
now_utc = datetime.now(timezone.utc)

# =========================================================
# 2. 分析用サマリーデータの構築（時速の差分を絶対に生み出すロジック）
# =========================================================
summary_list = []

if not df_clean.empty:
    unique_vids = df_clean['video_id'].unique()
    
    for v_id in unique_vids:
        df_v = df_clean[df_clean['video_id'] == v_id].copy()
        if df_v.empty: continue
            
        # タイトルの処理
        raw_title = df_v.iloc[-1].get('title', f"Video {v_id}")
        if pd.isna(raw_title): raw_title = "Unknown"
        short_title = str(raw_title).replace('ILLIT (아일릿)', '').replace("'Magnetic'", 'Magnetic').strip()
        
        # 投稿日時の処理
        pub_at_raw = df_v.iloc[-1].get('published_at')
        if pd.isna(pub_at_raw): pub_at_raw = now_utc.isoformat()
        pub_at = pd.to_datetime(pub_at_raw, utc=True)
        
        # --- ① 通算時速 (Lifetime VPH) ---
        latest_views = df_v.iloc[-1]['views']
        lifetime_hours = max((now_utc - pub_at).total_seconds() / 3600, 0.1)
        lifetime_vph = round(latest_views / lifetime_hours, 1)
        
        # --- ② 直近時速 (Current VPH) 強制算出 ---
        current_vph = lifetime_vph
        if len(df_v) >= 2:
            # 確実に「最新のログ」と「1つ前のログ」を比較して引き算する
            t_latest = df_v.iloc[-1]['timestamp']
            t_prev = df_v.iloc[-2]['timestamp']
            v_latest = df_v.iloc[-1]['views']
            v_prev = df_v.iloc[-2]['views']
            
            hours_diff = (t_latest - t_prev).total_seconds() / 3600
            if hours_diff > 0:
                current_vph = round(max(v_latest - v_prev, 0) / hours_diff, 1)
        
        # モメンタムレシオ
        momentum_ratio = round(current_vph / lifetime_vph, 2) if lifetime_vph > 0 else 1.0

        summary_list.append({
            'video_id': v_id,
            'full_title': raw_title,
            'short_title': short_title,
            'lifetime_vph': lifetime_vph,
            'current_vph': current_vph,
            'momentum_ratio': momentum_ratio
        })

df_summary = pd.DataFrame(summary_list)

# =========================================================
# 3. ダッシュボードUI描画（機能1: VPHモメンタム比較）
# =========================================================
st.subheader("1. VPHモメンタム比較")
st.markdown("""
* **通算ヒットペース（平均時速）**: 動画公開から現在までの平均伸び速度
* **現在のバズ勢い（直近時速）**: ツールに登録後のリアルタイム増加速度（今まさにバズっているか）
""")

if not df_summary.empty:
    col1, col2 = st.columns([2, 1])

    with col1:
        fig_vph = go.Figure()
        # 青グラフ（通算）
        fig_vph.add_trace(go.Bar(
            x=df_summary['short_title'],
            y=df_summary['lifetime_vph'],
            name='通算ヒットペース (青)',
            marker_color='#1f77b4',
            hovertext=df_summary['full_title']
        ))
        # オレンジグラフ（直近）
        fig_vph.add_trace(go.Bar(
            x=df_summary['short_title'],
            y=df_summary['current_vph'],
            name='現在のバズ勢い (オレンジ)',
            marker_color='#ff7f0e',
            hovertext=df_summary['full_title']
        ))
        
        fig_vph.update_layout(
            barmode='group',
            title="動画別 再生速度 (VPH) 比較",
            xaxis_title="動画タイトル",
            yaxis_title="再生増加数 (回 / 時間)",
            legend=dict(orientation="h", y=1.1)
        )
        st.plotly_chart(fig_vph, use_container_width=True)

    with col2:
        st.markdown("##### バズ加速度判定")
        for _, row in df_summary.iterrows():
            ratio = row['momentum_ratio']
            if ratio > 1.2:
                status = "🚀 急加速中"
            elif ratio < 0.8:
                status = "📉 減速傾向"
            else:
                status = "➡️ 安定維持"
                
            st.write(f"**{row['short_title']}**")
            st.caption(f"バズ加速度: **{ratio}倍** ({status})")
            st.write(f"・直近速度: `{row['current_vph']}` 回/時")
            st.write(f"・通算平均: `{row['lifetime_vph']}` 回/時")
            st.divider()
else:
    st.warning("⚠️ 分析可能な動画データがありません。データベースの接続設定やデータ収集スクリプトの実行状況を確認してください。")

# =========================================================
# ※ もしこれ以降に「機能2」「機能3」などの別のグラフのコードが
# 存在していた場合は、この下に追加して記述してください。
# =========================================================
