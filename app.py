import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="代谢物注释差异分析", layout="wide")
st.title("🧪 代谢物注释差异分析：non-ds vs ds")
st.markdown("比较 metDNA 校正前后的注释结果，找出 `non-ds` 中有而 `ds` 中没有的代谢物名称。")

# 容差参数调节
st.sidebar.header("⚙️ 匹配参数")
mz_tol = st.sidebar.number_input("mz 容差 (Da)", value=0.01, step=0.001, format="%.4f")
rt_tol = st.sidebar.number_input("保留时间容差 (min)", value=0.5, step=0.1, format="%.2f")

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

    # 筛选正离子模式（adduct 列包含 '+'）
    if 'adduct' in non_df.columns and 'adduct' in ds_df.columns:
        non_pos = non_df[non_df['adduct'].str.contains(r'\+', na=False)].copy()
        ds_pos = ds_df[ds_df['adduct'].str.contains(r'\+', na=False)].copy()
    else:
        st.error("文件中缺少 'adduct' 列，无法区分正负离子。")
        st.stop()

    st.write(f"正离子模式行数: non-ds = {len(non_pos)}  |  ds = {len(ds_pos)}")
    if len(non_pos) == 0 or len(ds_pos) == 0:
        st.warning("正离子模式无数据，请检查 adduct 列是否包含 '+' 符号（例如 [M+H]+）")
        st.stop()

    # 构建 ds 特征的字典：key = (mz, rt) 近似匹配时使用容差
    # 为了快速匹配，将 ds 数据转化为列表
    ds_features = ds_pos[['mz', 'rt', 'name']].dropna().values.tolist()

    # 分组 non 特征
    non_groups = non_pos.groupby(['mz', 'rt'])
    
    diff_records = []
    candidate_reduce_count = 0
    missing_features = 0
    matched_features = 0

    # 遍历每个 non 特征
    for (mz_n, rt_n), group in non_groups:
        names_set = set(group['name'].dropna())
        
        # 在 ds 中寻找匹配的特征（第一个满足容差的）
        matched = False
        for mz_d, rt_d, name_d in ds_features:
            if abs(mz_n - mz_d) <= mz_tol and abs(rt_n - rt_d) <= rt_tol:
                matched = True
                matched_features += 1
                # 检查 name_d 是否在该特征的名称集合中（注意 ds 中同一特征可能有多个名称）
                # 我们需要收集 ds 中该特征下的所有名称
                # 更严谨：先找出所有匹配的 ds 行（相同 mz,rt 容差内），构建名称集合
                # 下面简化：只拿第一个匹配的名称，可能漏掉同一特征的其他候选名
                # 改进：收集所有满足容差的 ds 行的名称
                matching_names = set()
                for mz_d2, rt_d2, name_d2 in ds_features:
                    if abs(mz_n - mz_d2) <= mz_tol and abs(rt_n - rt_d2) <= rt_tol:
                        matching_names.add(name_d2)
                missing = names_set - matching_names
                for name in missing:
                    diff_records.append({
                        '代谢物名称': name,
                        'mz (non)': mz_n,
                        'rt (non)': rt_n,
                        '匹配的 ds mz (示例)': mz_d,
                        '匹配的 ds rt (示例)': rt_d,
                        '差异类型': '候选名减少'
                    })
                    candidate_reduce_count += 1
                break  # 只要匹配上一个特征就处理完该 non 特征，不再重复匹配
        
        if not matched:
            # 整个特征在 ds 中无匹配
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
    st.write(f"- 成功匹配的特征数（至少一个名称匹配）: {matched_features} / {len(non_groups)}")

    if diff_records:
        diff_df = pd.DataFrame(diff_records)
        st.dataframe(diff_df, use_container_width=True)
        csv = diff_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 下载差异清单 CSV", csv, "metabolite_diff.csv", "text/csv")
    else:
        st.success("✅ 未发现差异！")

    # 调试信息：展示前几行
    with st.expander("🔎 查看上传文件的前几行（用于检查列名和格式）"):
        st.write("non-ds 前5行")
        st.dataframe(non_df.head())
        st.write("ds 前5行")
        st.dataframe(ds_df.head())
