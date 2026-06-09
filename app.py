import streamlit as st
import pandas as pd
import numpy as np
from scipy.spatial import cKDTree

st.set_page_config(page_title="代谢物注释差异分析（容差匹配）", layout="wide")
st.title("🧪 代谢物注释差异分析：non-ds vs ds（带容差）")

st.markdown("""
本工具使用 **容差匹配**（mz 误差 ≤ 0.01，rt 误差 ≤ 0.5 分钟）来对齐校正前后的特征，  
避免因四舍五入导致的误判。
""")

col1, col2 = st.columns(2)
with col1:
    non_file = st.file_uploader("上传 non-ds 文件（原始注释）", type=["csv"])
with col2:
    ds_file = st.file_uploader("上传 ds 文件（校正后注释）", type=["csv"])

if non_file and ds_file:
    non_df = pd.read_csv(non_file)
    ds_df = pd.read_csv(ds_file)

    st.subheader("📄 文件概览")
    st.write(f"non-ds 总行数: {len(non_df)}  |  ds 总行数: {len(ds_df)}")

    # 筛选正离子模式（假设 adduct 列包含 '+'）
    non_pos = non_df[non_df['adduct'].str.contains(r'\+', na=False)].copy()
    ds_pos = ds_df[ds_df['adduct'].str.contains(r'\+', na=False)].copy()

    st.write(f"正离子模式行数: non-ds = {len(non_pos)}  |  ds = {len(ds_pos)}")
    if len(non_pos) == 0 or len(ds_pos) == 0:
        st.error("未检测到正离子数据，请检查 adduct 列是否包含 '+' 符号。")
        st.stop()

    # 提取特征矩阵 (mz, rt)
    non_features = non_pos[['mz', 'rt']].drop_duplicates().values
    ds_features = ds_pos[['mz', 'rt']].drop_duplicates().values

    # 构建 ds 的 KDTree
    if len(ds_features) > 0:
        tree = cKDTree(ds_features)
        # 查询每个 non 特征在 ds 中的最近邻，距离阈值：mz 差 0.01，rt 差 0.5
        # 注意：需要归一化或分别设置阈值，这里简单将 (mz, rt) 缩放后计算欧氏距离
        # 更精确：分别判断 mz_diff <= 0.01 and rt_diff <= 0.5
        # 使用自定义匹配逻辑（避免尺度问题）
        matched_indices = {}
        for i, (mz_n, rt_n) in enumerate(non_features):
            best_idx = None
            best_diff = float('inf')
            for j, (mz_d, rt_d) in enumerate(ds_features):
                if abs(mz_n - mz_d) <= 0.01 and abs(rt_n - rt_d) <= 0.5:
                    # 找到第一个满足条件的即可（也可选最近）
                    matched_indices[i] = j
                    break
    else:
        matched_indices = {}

    st.write(f"成功匹配的特征对数量: {len(matched_indices)} / {len(non_features)}")

    # 构建 ds 中每个匹配特征下的名称集合
    ds_dict = {}
    for idx_d, row in ds_pos.iterrows():
        key = (row['mz'], row['rt'])
        ds_dict.setdefault(key, set()).add(row['name'])

    # 构建 non 中每个特征下的名称集合，并匹配
    diff_records = []
    candidate_reduce_count = 0
    missing_features = 0

    # 先按特征分组
    non_groups = non_pos.groupby(['mz', 'rt'])
    for (mz_n, rt_n), group in non_groups:
        names_set = set(group['name'].dropna())
        # 寻找匹配的 ds 特征
        matched = False
        for (mz_d, rt_d), ds_names in ds_dict.items():
            if abs(mz_n - mz_d) <= 0.01 and abs(rt_n - rt_d) <= 0.5:
                matched = True
                missing = names_set - ds_names
                for name in missing:
                    diff_records.append({
                        '代谢物名称': name,
                        'mz (non)': mz_n,
                        'rt (non)': rt_n,
                        '匹配的 ds mz': mz_d,
                        '匹配的 ds rt': rt_d,
                        '差异类型': '候选名减少'
                    })
                    candidate_reduce_count += 1
                break
        if not matched:
            # 整个特征未匹配
            for name in names_set:
                diff_records.append({
                    '代谢物名称': name,
                    'mz (non)': mz_n,
                    'rt (non)': rt_n,
                    '匹配的 ds mz': None,
                    '匹配的 ds rt': None,
                    '差异类型': '整个特征消失'
                })
                missing_features += 1

    st.subheader("🔍 差异代谢物清单")
    st.write(f"共发现 **{len(diff_records)}** 个代谢物名称在 non-ds 中存在但在 ds 中缺失。")
    st.write(f"- 其中 **{candidate_reduce_count}** 个属于同一特征下候选名减少")
    st.write(f"- 其中 **{missing_features}** 个属于整个特征消失")

    if diff_records:
        diff_df = pd.DataFrame(diff_records)
        st.dataframe(diff_df, use_container_width=True)
        csv = diff_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 下载差异清单 CSV", csv, "metabolite_diff.csv", "text/csv")
    else:
        st.success("✅ 未发现差异！")

    # 显示前几行数据供检查
    with st.expander("🔎 查看上传文件的前几行（用于调试）"):
        st.write("non-ds 前5行")
        st.dataframe(non_df.head())
        st.write("ds 前5行")
        st.dataframe(ds_df.head())
