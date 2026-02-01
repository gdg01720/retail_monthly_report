import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import io
import os
import base64
from datetime import datetime

import matplotlib.font_manager as fm

# フォントファイルのパス（fontsフォルダに置いた場合）
font_path = os.path.join(os.path.dirname(__file__), "fonts", "ipaexg.ttf")
if os.path.exists(font_path):
    fm.fontManager.addfont(font_path)
    plt.rcParams['font.family'] = 'IPAexGothic'

# --- 1. フォント・基本設定 ---
# Windows環境(Meiryo)とLinux環境の両方に対応するためのリスト指定
#plt.rcParams['font.family'] = ['Meiryo', 'MS Gothic', 'DejaVu Sans', 'sans-serif']
sns.set_theme(style="whitegrid", rc={"font.family": ['IPAexGothic', 'Meiryo', 'MS Gothic', 'sans-serif']})

st.set_page_config(page_title="小売業月次レポート", layout="wide")

# --- 2. 企業グループ定義 ---
GROUPS = {
    'イオングループ': ['イオンリテール', 'イオン北海道', 'イオン九州', 'マックスバリュー東海', 'フジ・リテイリング', 'U.S.M.H','ツルハ', 'ミニストップ'],
    'ドラッグストア': ['ツルハ', 'マツキヨココカラ', 'コスモス薬品','クリエイトSD', 'サンドラッグ', 'スギ薬局', 'クスリのアオキ', 'サツドラ', '薬王堂'],
    'ホームセンター': ['DCMHD', 'コーナン', 'コメリ', 'アークランズ','ジョイフル本田'],
    'スーパーマーケット（全国）': ['イオンリテール', 'PPIH', 'トライアル'],
    'スーパーマーケット（東日本）': ['イオン北海道', 'アークス', 'ヤオコー', 'ライフ',  'ベルク', 'U.S.M.H'],
    'スーパーマーケット（西日本）': ['平和堂', 'バロー', 'イズミ', 'ライフ', 'ハローズ', 'イオン九州', 'マックスバリュー東海', 'フジ・リテイリング']
}

# --- 3. ロジック関数 ---
def load_data():
    """実行スクリプトの場所を基準に data フォルダを探す（より堅牢な方法）"""
    # 1. app.py が置かれているディレクトリの絶対パスを取得
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 2. その下の data/retail_data.xlsx を指すパスを作成
    path = os.path.join(current_dir, "data", "retail_data.xlsx")
    
    # デバッグ用：探しているパスを画面に出さずにログ（Manage app）に記録する
    # print(f"Looking for file at: {path}")

    if os.path.exists(path):
        return pd.read_excel(path), path
    
    # もし見つからない場合、念のため直下の data フォルダも探す
    alternative_path = os.path.join("data", "retail_data.xlsx")
    if os.path.exists(alternative_path):
        return pd.read_excel(alternative_path), alternative_path
        
    return None, None

def process_and_filter(df, companies, end_month_str):
    df = df[df['企業名'].isin(companies)].copy()
    df['dt'] = pd.to_datetime(df['月次'], errors='coerce')
    df = df.dropna(subset=['dt'])
    
    latest_dt = pd.to_datetime(end_month_str)
    start_dt = latest_dt - pd.DateOffset(months=12)
    df = df[(df['dt'] >= start_dt) & (df['dt'] <= latest_dt)]
    
    def create_pivot(sub_df):
        if sub_df.empty: return pd.DataFrame()
        pivot = pd.crosstab(sub_df['企業名'], sub_df['月次'], values=sub_df['対前年比'], aggfunc='sum')
        cols = sorted(pivot.columns, reverse=True)
        if cols: pivot = pivot.sort_values(cols[0], ascending=False)
        return pivot

    return create_pivot(df[df['全店/既存店'] == '全店']), create_pivot(df[df['全店/既存店'] == '既存店'])

# --- チャート生成関数（修正なしですが確認用） ---
def create_chart(table, title):
    if table.empty: return None
    fig, ax = plt.subplots(figsize=(12, 6))
    sorted_cols = sorted(table.columns)
    for i in table.index:
        ax.plot(sorted_cols, table.loc[i, sorted_cols], marker="o", label=i)
    ax.axhline(100, color='black', linestyle='--', linewidth=1, alpha=0.5)
    ax.set_title(title, fontsize=16)
    plt.xticks(rotation=45)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    return fig

# --- HTMLレポート生成関数（CSSを強化） ---
def get_html_report(dfs_with_titles, figs_with_titles):
    # font-family に Meiryo を追加
    html = "<html><head><meta charset='utf-8'><style>body{font-family:'Meiryo', 'MS Gothic', sans-serif; padding:20px;} table{border-collapse:collapse; width:100%; margin-bottom:30px;} th,td{border:1px solid #ccc; padding:8px; text-align:right;} th{background:#f4f4f4; text-align:center;}</style></head><body>"
    html += "<h1>月次業績レポート</h1>"
    for title, df in dfs_with_titles.items():
        if not df.empty:
            html += f"<h2>{title}</h2>" + df.to_html()
    for title, fig in figs_with_titles.items():
        if fig:
            buf = io.BytesIO()
            fig.savefig(buf, format="png", bbox_inches='tight')
            data = base64.b64encode(buf.getbuffer()).decode("ascii")
            html += f"<h2>{title} チャート</h2><img src='data:image/png;base64,{data}' style='max-width:100%;'/><br>"
    html += "</body></html>"
    return html
# --- 4. メイン UI ---
st.title("📊 小売業 月次業績ダッシュボード")

df_raw, actual_path = load_data()

if df_raw is not None:
    df_raw['temp_dt'] = pd.to_datetime(df_raw['月次'], errors='coerce')
    available_months = sorted(df_raw['temp_dt'].dropna().unique(), reverse=True)
    month_options = [dt.strftime('%Y-%m') for dt in available_months]
    
    st.sidebar.header("分析条件")
    selected_pattern = st.sidebar.selectbox("表示パターン", list(GROUPS.keys()))
    selected_end_month = st.sidebar.selectbox("分析の終了月を選択", options=month_options, index=0)

    tab_all, tab_kison = process_and_filter(df_raw, GROUPS[selected_pattern], selected_end_month)

    st.header(f"対象: {selected_pattern} ({selected_end_month}まで)")
    c_chart, c_table = st.tabs(["📈 チャート", "📋 テーブル"])
    
    with c_chart:
        fig_a = create_chart(tab_all, f"【全店】{selected_pattern}")
        if fig_a: st.pyplot(fig_a)
        st.divider()
        fig_k = create_chart(tab_kison, f"【既存店】{selected_pattern}")
        if fig_k: st.pyplot(fig_k)

    with c_table:
        st.subheader("全店データ")
        st.dataframe(tab_all, use_container_width=True)
        st.subheader("既存店データ")
        st.dataframe(tab_kison, use_container_width=True)

    # 出力
    st.sidebar.markdown("---")
    st.sidebar.header("出力")
    out_ex = io.BytesIO()
    with pd.ExcelWriter(out_ex, engine='xlsxwriter') as wr:
        tab_all.to_excel(wr, sheet_name='全店')
        tab_kison.to_excel(wr, sheet_name='既存店')
    st.sidebar.download_button("Excel保存", out_ex.getvalue(), f"report_{selected_pattern}.xlsx")
    
    h_rep = get_html_report({"全店": tab_all, "既存店": tab_kison}, {"全店": fig_a, "既存店": fig_k})
    st.sidebar.download_button("HTML保存", h_rep, f"report_{selected_pattern}.html", "text/html")

else:
    # ここが NameError の原因箇所でした。修正済み。
    st.error("データファイルが見つかりません。")
    st.info("GitHubの 'data/' フォルダ内に 'retail_data.xlsx' という名前でファイルを配置してください。")