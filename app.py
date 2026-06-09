import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="代谢物注释差异分析", layout="wide")
st.title("🧪 代谢物注释差异分析：non-ds vs ds")
st.markdown("比较 metDNA 校正前后的注释结果，找出 `non-ds` 中有而 `ds` 中缺失的代谢物名称。")

# 侧边栏参数
st.sidebar.header("⚙️ 匹配参数")
mz_tol = st.sidebar.number_input("mz 容差 (Da)", value=0.01, step=0.001, format="%.4f", help="建议 0.01")
rt_tol = st.sidebar.number_input("保留时间容差 (min)", value=0.5, step=0.1, format="%.2f", help="建议 0.5")
pos_pattern = st.sidebar.text_input("正离子 adduct 包含的符号", value="+", help="例如 '+', '[M+H]+' 等")
neg_pattern = st.sidebar.text_input("负离子 adduct 包含的符号", value="-", help="例如 '-', '[M-H]-' 等")

st.sidebar.markdown("---")
st.sidebar.info("如果您的文件中 adduct 列格式特殊，请修改上面的匹配符号。")

# 文件上传
col1, col2 = st.columns(2)
with col1:
    non_file = st.file_uploader("上传 non-ds 文件（原始注释）", type=["csv"])
with col2:
    ds_file = st.file_uploader("上传 ds 文件（校正后注释）", type=["csv"])

if non_file and ds_file:
    non_df = pd.read_csv(non_file)
    ds_df = pd.read_csv(ds_file)

    st.subheader("📊 文件概览")
    st.write(f"non-ds 总行数: {len(non_df)}  |  ds 总行数: {len(ds_df)}")

    # 检查必要列
    required_cols = ['mz', 'rt', 'name', 'adduct']
    for col in required_cols:
        if col not in non_df.columns or col not in ds_df.columns:
            st.error(f"文件中缺少列 '{col}'，请确保列名正确（区分大小写）")
            st.stop()

    # 筛选正离子模式（根据用户输入的符号）
    non_pos = non_df[non_df['adduct'].str.contains(pos_pattern, na=False, regex=False)].copy()
    ds_pos = ds_df[ds_df['adduct'].str.contains(pos_pattern, na=False, regex=False)].copy()

    st.write(f"正离子模式行数: non-ds = {len(non_pos)}  |  ds = {len(ds_pos)}")

    if len(non_pos) == 0:
        st.warning(f"non-ds 文件中未找到包含 '{pos_pattern}' 的 adduct 行，请检查 adduct 列内容。")
        st.dataframe(non_df[['adduct']].drop_duplicates().head(10))
        st.stop()
    if len(ds_pos) == 0:
        st.warning(f"ds 文件中未找到包含 '{pos_pattern}' 的 adduct 行，请检查 adduct 列内容。")
        st.dataframe(ds_df[['adduct']].drop_duplicates().head(10))
        st.stop()

    # 提取特征并去重（同一个 mz,rt 可能有多个名称）
    non_groups = non_pos.groupby(['mz', 'rt'])['name'].apply(lambda x: set(x.dropna())).reset_index()
    ds_groups = ds_pos.groupby(['mz', 'rt'])['name'].apply(lambda x: set(x.dropna())).reset_index()

    # 将 ds 特征转为列表，用于容差匹配
    ds_features = []
    for _, row in ds_groups.iterrows():
        ds_features.append((row['mz'], row['rt'], row['name']))

    # 匹配
    diff_records = []
    candidate_reduce = 0
    feature_missing = 0
    matched_feature_count = 0

    for _, row in non_groups.iterrows():
        mz_n, rt_n = row['mz'], row['rt']
        names_n = row['name']

        # 在 ds 中查找匹配特征
        best_match = None
        best_dist = float('inf')
        for mz_d, rt_d, names_d in ds_features:
            if abs(mz_n - mz_d) <= mz_tol and abs(rt_n - rt_d) <= rt_tol:
                dist = np.sqrt((mz_n - mz_d)**2 + (rt_n - rt_d)**2)
                if dist < best_dist:
                    best_dist = dist
                    best_match = (mz_d, rt_d, names_d)

        if best_match is not None:
            matched_feature_count += 1
            mz_d, rt_d, names_d = best_match
            missing_names = names_n - names_d
            if missing_names:
                for name in missing_names:
                    diff_records.append({
                        '代谢物名称': name,
                        'mz (non)': mz_n,
                        'rt (non)': rt_n,
                        '匹配的 ds mz': mz_d,
                        '匹配的 ds rt': rt_d,
                        '差异类型': '候选名减少'
                    })
                    candidate_reduce += 1
        else:
            # 整个特征未匹配
            for name in names_n:
                diff_records.append({
                    '代谢物名称': name,
                    'mz (non)': mz_n,
                    'rt (non)': rt_n,
                    '匹配的 ds mz': None,
                    '匹配的 ds rt': None,
                    '差异类型': '整个特征消失'
                })
                feature_missing += 1

    st.subheader("🔍 差异分析结果")
    st.write(f"non-ds 中的特征总数（按 mz,rt 去重）: {len(non_groups)}")
    st.write(f"成功匹配到 ds 的特征数: {matched_feature_count}")
    st.write(f"未匹配的特征数（整个特征消失）: {len(non_groups) - matched_feature_count}")
    st.write(f"**总差异代谢物名称数**: {len(diff_records)}")
    st.write(f"- 其中候选名减少: {candidate_reduce}")
    st.write(f"- 其中整个特征消失: {feature_missing}")

    if diff_records:
        diff_df = pd.DataFrame(diff_records)
        st.dataframe(diff_df, use_container_width=True)
        # 修复乱码：使用 utf-8-sig 编码
        csv_data = diff_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下载差异清单 CSV", csv_data, "metabolite_diff.csv", "text/csv")
    else:
        st.success("✅ 未发现差异！")

    # 调试信息
    with st.expander("🔎 查看数据样例（用于调试）"):
        st.write("non-ds 正离子模式前10行")
        st.dataframe(non_pos.head(10))
        st.write("ds 正离子模式前10行")
        st.dataframe(ds_pos.head(10))
        st.write("non-ds 特征分组示例")
        st.dataframe(non_groups.head())
        st.write("ds 特征分组示例")
        st.dataframe(ds_groups.head())
