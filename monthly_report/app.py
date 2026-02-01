import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import io
import os
import base64
from datetime import datetime

# --- 1. 基本設定 ---
# Streamlit Cloud (Linux) 環境でも日本語が化けないよう、
# 後ほど「font」フォルダにフォントファイルを入れる方法が最も確実ですが、
# まずは環境内のフォントを使用する設定にします。
plt.rcParams['font.family'] = ['Meiryo', 'MS Gothic', 'sans-serif'] 
sns.set_theme(style="whitegrid", rc={"font.family": "Meiryo"})

st.set_page_config(page_title="小売業月次業績レポート", layout="wide")

# --- 2. 企業グループ定義 ---
GROUPS = {
    'イオングループ': ['イオンリテール', 'イオン北海道', 'イオン九州', 'マックスバリュー東海', 'フジ・リテイリング', 'U.S.M.H','ツルハ', 'ミニストップ'],
    'ドラッグストア': ['ツルハ', 'マツキヨココカラ', 'コスモス薬品','クリエイトSD', 'サンドラッグ', 'スギ薬局', 'クスリのアオキ', 'サツドラ', '薬王堂'],
    'ホームセンター': ['DCMHD', 'コーナン', 'コメリ', 'アークランズ','ジョイフル本田'],
    'スーパーマーケット（全国）': ['イオンリテール', 'PPIH', 'トライアル'],
    'スーパーマーケット（東日本）': ['イオン北海道', 'アークス', 'ヤオコー', 'ライフ',  'ベルク', 'U.S.M.H'],
    'スーパーマーケット（西日本）': ['平和堂', 'バロー', 'イズミ', 'ライフ', 'ハローズ', 'イオン九州', 'マックスバリュー東海', 'フジ・リテイリング']
}

# --- 3. 自動ファイル読み込み ---
def load_latest_data():
    # パス指定を画面から消し、プログラム内部で解決
    # dataフォルダ内のxlsxファイルを探す
    data_dir = "data"
    if not os.path.exists(data_dir):
        return None
    
    files = [f for f in os.listdir(data_dir) if f.endswith('.xlsx')]
    if not files:
        return None
    
    # 常に最新の（ファイル名順で最後、または特定の名前）を読み込む
    # ここでは "retail_data.xlsx" という名前に固定して運用することを推奨
    target_file = os.path.join(data_dir, "retail_data.xlsx")
    if os.path.exists(target_file):
        return pd.read_excel(target_file)
    
    # 固定名がない場合は、フォルダ内の最初のxlsxを読み込む
    return pd.read_excel(os.path.join(data_dir, files[0]))

def process_and_filter(df, companies, end_month_str):
    """データの絞り込みと集計テーブルの作成"""
    df = df[df['企業名'].isin(companies)].copy()
    
    # 日付変換
    df['dt'] = pd.to_datetime(df['月次'], errors='coerce')
    df = df.dropna(subset=['dt'])
    
    # ユーザーが選択した「終了月」を基準にする
    latest_dt = pd.to_datetime(end_month_str)
    start_dt = latest_dt - pd.DateOffset(months=12)
    
    # 指定期間内のみ抽出（未来のデータはこの時点で除外される）
    df = df[(df['dt'] >= start_dt) & (df['dt'] <= latest_dt)]
    
    # 0や空のデータをグラフに反映させないための処理
    # (対前年比が0またはNaNの行を除外したい場合はここに追加可能ですが、
    # 期間指定で絞り込んでいるため通常は不要です)
    
    latest_month_label = latest_dt.strftime('%Y-%m')

    def create_pivot(sub_df):
        if sub_df.empty: return pd.DataFrame()
        pivot = pd.crosstab(
            sub_df['企業名'], sub_df['月次'], 
            values=sub_df['対前年比'], aggfunc='sum'
        )
        # 存在する列の中での最新月でソート
        cols = sorted(pivot.columns, reverse=True)
        if cols:
            pivot = pivot.sort_values(cols[0], ascending=False)
        return pivot

    table_all = create_pivot(df[df['全店/既存店'] == '全店'])
    table_kison = create_pivot(df[df['全店/既存店'] == '既存店'])
    
    return table_all, table_kison

def create_chart(table, title):
    if table.empty: return None
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # 列名（日付文字列）をソートして描画
    sorted_cols = sorted(table.columns)
    plot_data = table[sorted_cols]
    
    for i in plot_data.index:
        # 0の値をプロットしたくない場合は mask を使うなどの処理が必要ですが、
        # 期間で区切っているため、期間内の0は「実績0」として表示されます
        ax.plot(plot_data.columns, plot_data.loc[i], marker="o", label=i)
    
    ax.axhline(100, color='black', linestyle='--', linewidth=1, alpha=0.5)
    ax.set_title(title, fontsize=16)
    ax.set_ylabel("対前年比 (%)")
    plt.xticks(rotation=45)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    return fig

# (HTMLレポート生成関数は前回と同様のため省略可ですが、一貫性のために保持)
def get_html_report(dfs_with_titles, figs_with_titles):
    html = "<html><head><meta charset='utf-8'><style>body{font-family:Meiryo; padding:20px;} table{border-collapse:collapse; width:100%; margin-bottom:30px;} th,td{border:1px solid #ccc; padding:8px; text-align:right;} th{background:#f4f4f4;} .name{text-align:left;}</style></head><body>"
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

df_raw = load_latest_data()

if df_raw is not None:
    # データ内の有効な年月リストを取得して選択肢にする
    df_raw['temp_dt'] = pd.to_datetime(df_raw['月次'], errors='coerce')
    available_months = sorted(df_raw['temp_dt'].dropna().unique(), reverse=True)
    month_options = [dt.strftime('%Y-%m') for dt in available_months]
    
    st.sidebar.header("分析条件")
    selected_pattern = st.sidebar.selectbox("表示パターン", list(GROUPS.keys()))
    selected_end_month = st.sidebar.selectbox(
        "分析の終了月を選択",
        options=month_options,
        index=0
    )

    # フィルタリング実行と表示
    tab_all, tab_kison = process_and_filter(df_raw, GROUPS[selected_pattern], selected_end_month)

# チャートとテーブルの表示
    col_chart, col_table = st.tabs(["📈 チャート", "📋 テーブル"])
    
    with col_chart:
        fig_all = create_chart(tab_all, f"【全店】{selected_pattern} 推移 ({selected_end_month}まで)")
        if fig_all: st.pyplot(fig_all)
        
        st.divider()
        
        fig_kison = create_chart(tab_kison, f"【既存店】{selected_pattern} 推移 ({selected_end_month}まで)")
        if fig_kison: st.pyplot(fig_kison)

    with col_table:
        st.subheader("全店データ")
        st.dataframe(tab_all)
        st.subheader("既存店データ")
        st.dataframe(tab_kison)

# --- ダウンロード機能 ---
    st.sidebar.markdown("---")
    st.sidebar.header("ダウンロード")
    
    # Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        tab_all.to_excel(writer, sheet_name='全店')
        tab_kison.to_excel(writer, sheet_name='既存店')
    
    st.sidebar.download_button(
        "Excelファイルを保存", 
        output.getvalue(), 
        file_name=f"月次レポート_{selected_pattern}.xlsx"
    )

    # HTML
    html_report = get_html_report(
        {"全店データ": tab_all, "既存店データ": tab_kison},
        {"全店": fig_all, "既存店": fig_kison}
    )
    st.sidebar.download_button(
        "HTMLレポートを保存", 
        html_report, 
        file_name=f"月次レポート_{selected_pattern}.html",
        mime="text/html"
    )

else:
    st.error(f"ファイルが見つかりません: {file_path_input}")
    st.info("正しいパスを入力するか、GitHubにアップロードした際は相対パス（例: data/file.xlsx）を入力してください。")


