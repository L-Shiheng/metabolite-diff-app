import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="代谢物注释差异对比", layout="wide")
st.title("🧪 代谢物注释差异对比：non-ds vs ds")
st.markdown("逐个离子对比校正前后的候选代谢物名称，清晰显示异构体变化（减少/增加/改变）。")

# 侧边栏参数
st.sidebar.header("⚙️ 匹配参数")
mz_tol = st.sidebar.number_input("mz 容差 (Da)", value=0.01, step=0.001, format="%.4f")
rt_tol = st.sidebar.number_input("保留时间容差 (min)", value=0.5, step=0.1, format="%.2f")
pos_pattern = st.sidebar.text_input("正离子 adduct 包含的符号", value="+")
neg_pattern = st.sidebar.text_input("负离子 adduct 包含的符号", value="-")

# 文件上传
col1, col2 = st.columns(2)
with col1:
    non_file = st.file_uploader("上传 non-ds 文件", type=["csv"])
with col2:
    ds_file = st.file_uploader("上传 ds 文件", type=["csv"])

def parse_names(names_series):
    """将 name 列（可能包含分号）解析为集合，去除空格"""
    all_names = set()
    for v in names_series.dropna():
        for part in str(v).split(';'):
            name = part.strip()
            if name:
                all_names.add(name)
    return all_names

if non_file and ds_file:
    non_df = pd.read_csv(non_file)
    ds_df = pd.read_csv(ds_file)

    # 检查列
    required = ['mz', 'rt', 'name', 'adduct']
    for col in required:
        if col not in non_df.columns or col not in ds_df.columns:
            st.error(f"缺少列: {col}")
            st.stop()

    # 筛选正离子（也可根据需求选择负离子，示例为正离子）
    non_pos = non_df[non_df['adduct'].str.contains(pos_pattern, na=False, regex=False)].copy()
    ds_pos = ds_df[ds_df['adduct'].str.contains(pos_pattern, na=False, regex=False)].copy()

    if len(non_pos) == 0 or len(ds_pos) == 0:
        st.warning("正离子模式无数据，请检查 adduct 列或切换离子模式。")
        st.dataframe(non_df[['adduct']].drop_duplicates())
        st.stop()

    # 按 (mz, rt) 分组，合并同一特征下的所有 name（用集合）
    non_groups = non_pos.groupby(['mz', 'rt'])['name'].apply(parse_names).reset_index()
    ds_groups = ds_pos.groupby(['mz', 'rt'])['name'].apply(parse_names).reset_index()
    ds_features = [(row['mz'], row['rt'], row['name']) for _, row in ds_groups.iterrows()]

    details = []

    for _, row in non_groups.iterrows():
        mz_n, rt_n = row['mz'], row['rt']
        names_n = row['name']   # 这是一个 set

        # 查找匹配的 ds 特征（最小欧氏距离）
        best = None
        best_dist = float('inf')
        for mz_d, rt_d, names_d in ds_features:
            if abs(mz_n - mz_d) <= mz_tol and abs(rt_n - rt_d) <= rt_tol:
                dist = np.sqrt((mz_n - mz_d)**2 + (rt_n - rt_d)**2)
                if dist < best_dist:
                    best_dist = dist
                    best = (mz_d, rt_d, names_d)

        if best is not None:
            mz_d, rt_d, names_d = best
            # 集合比较
            if names_n == names_d:
                diff_type = "无差异"
                missing_names = set()
                reason = "校正后候选名无变化（仅顺序可能不同）"
            elif names_n.issuperset(names_d) and names_n != names_d:
                diff_type = "候选名减少"
                missing_names = names_n - names_d
                reason = f"校正后移除了以下异构体: {'; '.join(sorted(missing_names))}"
            elif names_d.issuperset(names_n) and names_d != names_n:
                diff_type = "候选名增加"
                missing_names = set()
                added = names_d - names_n
                reason = f"校正后新增了以下异构体: {'; '.join(sorted(added))}"
            else:
                diff_type = "候选名改变"
                missing_names = names_n - names_d
                added = names_d - names_n
                reason = f"校正后异构体发生变化，移除了: {'; '.join(sorted(missing_names))}; 新增了: {'; '.join(sorted(added))}"
        else:
            # 整个特征消失
            diff_type = "整个特征消失"
            missing_names = names_n
            reason = "校正后该 mz-rt 特征未匹配到任何代谢物"

        details.append({
            'mz_non': mz_n, 'rt_non': rt_n,
            'mz_ds': best[0] if best else '', 'rt_ds': best[1] if best else '',
            'non_names': '; '.join(sorted(names_n)),
            'ds_names': '; '.join(sorted(best[2])) if best else '',
            'missing_names': '; '.join(sorted(missing_names)),
            'diff_type': diff_type,
            'reason': reason
        })

    diff_df = pd.DataFrame(details)
    # 只保留有差异的行（排除无差异）
    diff_df = diff_df[diff_df['diff_type'] != '无差异'].reset_index(drop=True)

    st.subheader("📊 特征级对比明细")
    st.write(f"共有 **{len(diff_df)}** 个特征存在差异")
    for t in diff_df['diff_type'].unique():
        st.write(f"- {t}: {len(diff_df[diff_df['diff_type']==t])} 个")

    # 简洁表格（隐藏 reason 列，避免过宽）
    st.dataframe(diff_df[['mz_non', 'rt_non', 'non_names', 'ds_names', 'missing_names', 'diff_type']],
                 use_container_width=True)

    # 生成 HTML 详细报告（带颜色标注）
    html = f"""
    <html>
    <head><meta charset="UTF-8"><title>代谢物注释差异对比报告</title>
    <style>
        body {{ font-family: Arial; margin: 20px; }}
        table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; vertical-align: top; }}
        th {{ background-color: #f2f2f2; }}
        .missing {{ color: red; font-weight: bold; }}
        .added {{ color: green; }}
        .feature-gone {{ background-color: #ffe6e6; }}
        .change {{ background-color: #fff3e0; }}
    </style>
    </head>
    <body>
        <h2>代谢物注释差异对比报告</h2>
        <p>生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <table>
            <thead><tr><th>mz (non)</th><th>rt (non)</th><th>non-ds 候选名</th><th>ds 候选名</th><th>缺失/变化明细</th><th>差异类型</th><th>原因说明</th></tr></thead>
            <tbody>
    """

    for _, row in diff_df.iterrows():
        if row['diff_type'] == '整个特征消失':
            cls = "class='feature-gone'"
        elif row['diff_type'] == '候选名改变':
            cls = "class='change'"
        else:
            cls = ""
        missing_html = f"<span class='missing'>{row['missing_names']}</span>" if row['missing_names'] else ""
        html += f"<tr {cls}><td>{row['mz_non']}</td><td>{row['rt_non']}</td>"
        html += f"<td>{row['non_names']}</td><td>{row['ds_names']}</td>"
        html += f"<td>{missing_html}</td><td>{row['diff_type']}</td><td>{row['reason']}</td></tr>"

    html += """
            </tbody>
        </table>
        <p>注：红色字体表示在 ds 中缺失的代谢物名称；绿色字体表示新增（若出现在原因说明中）。</p>
    </body>
    </html>
    """

    st.components.v1.html(html, height=600, scrolling=True)

    st.download_button("📄 下载 HTML 报告", html.encode('utf-8'), "metabolite_diff_report.html", "text/html")
    csv_data = diff_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 下载 CSV 差异清单", csv_data, "metabolite_diff.csv", "text/csv")

    with st.expander("🔎 查看原始分组数据（调试）"):
        st.write("non-ds 特征分组 (前10)")
        st.dataframe(non_groups.head(10))
        st.write("ds 特征分组 (前10)")
        st.dataframe(ds_groups.head(10))
