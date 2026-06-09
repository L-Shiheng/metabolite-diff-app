import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="代谢物注释差异分析", layout="wide")
st.title("🧪 代谢物注释差异分析：non-ds vs ds")
st.markdown("比较 metDNA 校正前后的注释结果，找出 `non-ds` 中有而 `ds` 中没有的代谢物名称。")

# 文件上传
col1, col2 = st.columns(2)
with col1:
    non_file = st.file_uploader("上传 non-ds 文件（原始注释）", type=["csv"])
with col2:
    ds_file = st.file_uploader("上传 ds 文件（校正后注释）", type=["csv"])

if non_file and ds_file:
    # 读取
    non_df = pd.read_csv(non_file)
    ds_df = pd.read_csv(ds_file)

    st.subheader("📊 文件概览")
    st.write(f"non-ds 总行数: {len(non_df)}  |  ds 总行数: {len(ds_df)}")

    # 只保留正离子模式（adduct 含 '+'）
    non_pos = non_df[non_df['adduct'].str.contains(r'\+', na=False)]
    ds_pos = ds_df[ds_df['adduct'].str.contains(r'\+', na=False)]

    st.write(f"正离子模式行数: non-ds = {len(non_pos)}  |  ds = {len(ds_pos)}")
    diff_count = len(non_pos) - len(ds_pos)
    st.info(f"📌 正离子模式差异总数: {diff_count} 行（仅计数，实际差异名称数见下方）")

    # 对齐 mz 和 rt（校正后通常保留4位小数，rt保留1位）
    non_pos['mz_key'] = non_pos['mz'].round(4)
    non_pos['rt_key'] = non_pos['rt'].round(1)
    ds_pos['mz_key'] = ds_pos['mz'].round(4)
    ds_pos['rt_key'] = ds_pos['rt'].round(1)

    # 构建 ds 中每个 (mz, rt) 下的名称集合
    ds_dict = {}
    for (mz, rt), group in ds_pos.groupby(['mz_key', 'rt_key']):
        ds_dict[(mz, rt)] = set(group['name'].dropna())

    # 收集差异
    diff_records = []
    missing_features = 0
    candidate_reduce_count = 0

    for (mz, rt), group in non_pos.groupby(['mz_key', 'rt_key']):
        names_set = set(group['name'].dropna())
        if (mz, rt) in ds_dict:
            missing = names_set - ds_dict[(mz, rt)]
            for name in missing:
                diff_records.append({
                    '代谢物名称': name,
                    'mz': mz,
                    'rt': rt,
                    '差异类型': '候选名减少（ds中该特征缺少此名称）'
                })
                candidate_reduce_count += 1
        else:
            # 整个特征在 ds 中不存在
            for name in names_set:
                diff_records.append({
                    '代谢物名称': name,
                    'mz': mz,
                    'rt': rt,
                    '差异类型': '整个特征消失（ds中无此mz-rt）'
                })
                missing_features += 1

    st.subheader("🔍 差异代谢物清单")
    st.write(f"共发现 **{len(diff_records)}** 个代谢物名称在 non-ds 中存在但在 ds 中缺失。")
    st.write(f"- 其中 **{candidate_reduce_count}** 个属于同一特征下候选名减少")
    st.write(f"- 其中 **{missing_features}** 个属于整个特征消失")

    if diff_records:
        diff_df = pd.DataFrame(diff_records)
        st.dataframe(diff_df, use_container_width=True)

        # 下载按钮
        csv = diff_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 下载差异清单 CSV",
            data=csv,
            file_name="metabolite_diff.csv",
            mime="text/csv"
        )
    else:
        st.success("✅ 未发现差异，两个文件完全一致！")

    # 显示示例
    with st.expander("📖 查看差异示例说明"):
        st.markdown("""
        **典型差异原因**：
        1. **候选名减少**：同一个 mz-rt 特征在 non-ds 中有多个代谢物名称，ds 中只保留了更可信的一个或多个。
        2. **整个特征消失**：校正后该 mz-rt 特征无法匹配到任何代谢物。
        
        **注意**：本应用只比较正离子模式（adduct 含 '+'）。负离子模式默认无差异。
        """)
else:
    st.info("请上传两个 CSV 文件开始分析")
