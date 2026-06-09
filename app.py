import pandas as pd
import sys

def parse_name_set(name_str):
    """将分号分隔的名称字符串解析为集合（去空格、去重）"""
    if pd.isna(name_str) or str(name_str).strip() == "":
        return set()
    # 按分号拆分，去除每个名称的首尾空格，过滤空字符串
    return {x.strip() for x in str(name_str).split(";") if x.strip()}

def determine_diff_type_and_missing(non_set, ds_set):
    """
    根据非校正集和校正集名称集合返回 (diff_type, missing_names_str)
    """
    missing = non_set - ds_set
    added = ds_set - non_set

    if non_set == ds_set:
        diff_type = "无变化"
        missing_str = ""
    elif missing and not added:
        # ds_set 是 non_set 的严格子集 → 候选名减少
        diff_type = "候选名减少"
        missing_str = ";".join(sorted(missing))
    elif added and not missing:
        # non_set 是 ds_set 的严格子集 → 候选名增加
        diff_type = "候选名增加"
        missing_str = ""   # 如需记录增加项可另加字段，这里保持 missing 为空
    else:
        # 既有增加又有减少，或相互替换
        diff_type = "候选名改变（有增有减）"
        missing_str = ";".join(sorted(missing))
    return diff_type, missing_str

def main(input_csv, output_csv=None):
    """
    读取输入 CSV，重新计算 diff_type 和 missing_names，输出到 output_csv
    若不指定 output_csv，自动在原文件名后加 _corrected
    """
    if output_csv is None:
        output_csv = input_csv.replace(".csv", "_corrected.csv")
    
    # 读取 CSV（注意处理可能的 BOM 头）
    df = pd.read_csv(input_csv, encoding="utf-8-sig")
    
    # 确保必要的列存在
    required_cols = ["non_names", "ds_names"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"输入 CSV 缺少必要列: {col}")
    
    # 为每一行计算新的 diff_type 和 missing_names
    new_diff_types = []
    new_missing_names = []
    
    for idx, row in df.iterrows():
        non_set = parse_name_set(row["non_names"])
        ds_set = parse_name_set(row["ds_names"])
        diff_type, missing_str = determine_diff_type_and_missing(non_set, ds_set)
        new_diff_types.append(diff_type)
        new_missing_names.append(missing_str)
    
    # 覆盖原有列（如果存在）或添加新列
    df["diff_type"] = new_diff_types
    df["missing_names"] = new_missing_names
    
    # 可选：如果存在 reason 列但不再需要，可以保留或重新生成
    # 这里保留原 reason 列，但您可以根据需要修改
    if "reason" in df.columns:
        # 可以根据新 diff_type 生成更准确的 reason，示例：
        new_reasons = []
        for diff_type, missing_str in zip(new_diff_types, new_missing_names):
            if diff_type == "候选名减少":
                reason = f"校正后移除了以下异构体: {missing_str}"
            elif diff_type == "候选名增加":
                reason = f"校正后新增了以下异构体: {ds_set - non_set}"  # 需额外计算
            elif diff_type == "无变化":
                reason = "校正后候选名无变化"
            else:
                reason = "校正后候选名发生增减/替换"
            new_reasons.append(reason)
        df["reason"] = new_reasons
    
    # 保存结果
    df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"处理完成！结果已保存至: {output_csv}")

if __name__ == "__main__":
    # 用法示例：直接修改下面的文件名，或在命令行运行
    # 方法1: 在代码中指定输入文件
    input_file = "metabolite_diff (2).csv"   # 改为您的实际文件名
    output_file = "metabolite_diff_corrected.csv"
    
    # 方法2: 从命令行参数获取
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        if len(sys.argv) > 2:
            output_file = sys.argv[2]
        else:
            output_file = input_file.replace(".csv", "_corrected.csv")
    
    main(input_file, output_file)
