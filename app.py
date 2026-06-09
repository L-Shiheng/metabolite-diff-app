import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="代谢物注释差异对比", layout="wide")
st.title("🧪 代谢物注释差异对比：non-ds vs ds")
st.markdown("逐个离子对比校正前后的候选代谢物名称，清晰显示减少了哪些异构体。")

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

if non_file and ds_file:
    non_df = pd.read_csv(non_file)
    ds_df = pd.read_csv(ds_file)

    # 检查列
    required = ['mz', 'rt', 'name', 'adduct']
    for col in required:
        if col not in non_df.columns or col not in ds_df.columns:
            st.error(f"缺少列: {col}")
            st.stop()

    # 筛选正离子
    non_pos = non_df[non_df['adduct'].str.contains(pos_pattern, na=False, regex=False)].copy()
    ds_pos = ds_df[ds_df['adduct'].str.contains(pos_pattern, na=False, regex=False)].copy()

    if len(non_pos) == 0 or len(ds_pos) == 0:
        st.warning("正离子模式无数据，请检查 adduct 列。")
        st.dataframe(non_df[['adduct']].drop_duplicates())
        st.stop()

    # 按 (mz, rt) 分组，收集名称集合
    non_groups = non_pos.groupby(['mz', 'rt'])['name'].apply(lambda x: set(x.dropna())).reset_index()
    ds_groups = ds_pos.groupby(['mz', 'rt'])['name'].apply(lambda x: set(x.dropna())).reset_index()
    ds_features = [(row['mz'], row['rt'], row['name']) for _, row in ds_groups.iterrows()]

    # 匹配并生成对比明细
    details = []  # 存储每个特征的对比信息

    for _, row in non_groups.iterrows():
        mz_n, rt_n = row['mz'], row['rt']
        names_n = row['name']

        # 查找匹配的 ds 特征
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
            missing = names_n - names_d
            if missing:
                diff_type = "候选名减少"
                reason = f"校正后移除了以下异构体: {'; '.join(sorted(missing))}"
            else:
                diff_type = "无差异"
                reason = ""
            details.append({
                'mz_non': mz_n, 'rt_non': rt_n,
                'mz_ds': mz_d, 'rt_ds': rt_d,
                'non_names': '; '.join(sorted(names_n)),
                'ds_names': '; '.join(sorted(names_d)),
                'missing_names': '; '.join(sorted(missing)) if missing else '',
                'diff_type': diff_type,
                'reason': reason
            })
        else:
            # 整个特征消失
            details.append({
                'mz_non': mz_n, 'rt_non': rt_n,
                'mz_ds': '', 'rt_ds': '',
                'non_names': '; '.join(sorted(names_n)),
                'ds_names': '',
                'missing_names': '; '.join(sorted(names_n)),
                'diff_type': '整个特征消失',
                'reason': '校正后该 mz-rt 特征未匹配到任何代谢物'
            })

    diff_df = pd.DataFrame(details)
    # 只保留有差异的行（候选名减少 或 特征消失）
    diff_df = diff_df[diff_df['diff_type'] != '无差异'].reset_index(drop=True)

    st.subheader("📊 特征级对比明细")
    st.write(f"共有 **{len(diff_df)}** 个特征存在差异（候选名减少或整个特征消失）")
    st.write(f"其中候选名减少的特征数: {len(diff_df[diff_df['diff_type']=='候选名减少'])}")
    st.write(f"其中整个特征消失的特征数: {len(diff_df[diff_df['diff_type']=='整个特征消失'])}")

    # 在 Streamlit 中显示表格（简洁版）
    st.dataframe(diff_df[['mz_non', 'rt_non', 'non_names', 'ds_names', 'missing_names', 'diff_type']],
                 use_container_width=True)

    # 生成 HTML 详细报告（带颜色标注）
    html = """
    <html>
    <head>
        <meta charset="UTF-8">
        <title>代谢物注释差异对比报告</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; vertical-align: top; }
            th { background-color: #f2f2f2; }
            .missing { color: red; font-weight: bold; }
            .feature-gone { background-color: #ffe6e6; }
        </style>
    </head>
    <body>
        <h2>代谢物注释差异对比报告</h2>
        <p>生成时间: """ + pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
        <table>
            <thead>
                <tr>
                    <th>mz (non)</th><th>rt (non)</th><th>non-ds 候选名</th>
                    <th>ds 候选名</th><th>缺失的候选名</th><th>差异类型</th><th>原因说明</th>
                </tr>
            </thead>
            <tbody>
    """

    for _, row in diff_df.iterrows():
        cls = "class='feature-gone'" if row['diff_type'] == '整个特征消失' else ""
        missing_html = f"<span class='missing'>{row['missing_names']}</span>" if row['missing_names'] else ""
        html += f"<tr {cls}>"
        html += f"<td>{row['mz_non']}</td><td>{row['rt_non']}</td>"
        html += f"<td>{row['non_names']}</td><td>{row['ds_names']}</td>"
        html += f"<td>{missing_html}</td><td>{row['diff_type']}</td><td>{row['reason']}</td>"
        html += "</tr>"

    html += """
            </tbody>
        </table>
        <p>注：红色字体表示在 ds 文件中缺失的代谢物名称。</p>
    </body>
    </html>
    """

    # 在 Streamlit 中直接显示 HTML（使用 components.html）
    st.components.v1.html(html, height=600, scrolling=True)

    # 下载 HTML 文件
    st.download_button(
        label="📄 下载 HTML 报告",
        data=html.encode('utf-8'),
        file_name="metabolite_diff_report.html",
        mime="text/html"
    )

    # 同时提供 CSV 下载
    csv_data = diff_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 下载 CSV 差异清单", csv_data, "metabolite_diff.csv", "text/csv")

    # 显示调试信息（可选）
    with st.expander("🔎 查看原始分组数据（调试）"):
        st.write("non-ds 特征分组")
        st.dataframe(non_groups.head(10))
        st.write("ds 特征分组")
        st.dataframe(ds_groups.head(10))
