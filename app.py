import pandas as pd
import sys

def parse_name_set(name_str):
    """将分号分隔的名称字符串解析为集合（去空格、去重）"""
    if pd.isna(name_str) or str(name_str).strip() == "":
        return set()
    return {x.strip() for x in str(name_str).split(";") if x.strip()}

def correct_row(row):
    """根据原始行的内容返回正确的 diff_type 和 missing_names"""
    non_set = parse_name_set(row["non_names"])
    ds_set = parse_name_set(row["ds_names"])
    
    # 判断是否为整个特征消失：mz_ds 为空或 ds_names 为空且 non_names 非空
    mz_ds_missing = pd.isna(row.get("mz_ds")) or str(row.get("mz_ds")).strip() == ""
    if mz_ds_missing and non_set and not ds_set:
        # 保持原“整个特征消失”不变
        return "整个特征消失", row["non_names"]  # 原 missing_names 通常就是 non_names
    
    # 否则，根据集合比较重新生成 diff_type 和 missing_names
    missing = non_set - ds_set
    added = ds_set - non_set
    
    if non_set == ds_set:
        diff_type = "无变化"
        missing_str = ""
    elif missing and not added:
        diff_type = "候选名减少"
        missing_str = ";".join(sorted(missing))
    elif added and not missing:
        diff_type = "候选名增加"
        missing_str = ""
    else:
        diff_type = "候选名改变"
        missing_str = ";".join(sorted(missing))
    
    return diff_type, missing_str

def generate_reason(diff_type, missing_str, non_set, ds_set):
    """根据 diff_type 生成 reason 文本"""
    if diff_type == "整个特征消失":
        return "校正后该 mz-rt 特征未匹配到任何代谢物"
    elif diff_type == "无变化":
        return "校正后候选名无变化（仅顺序可能调整）"
    elif diff_type == "候选名减少":
        return f"校正后移除了以下异构体: {missing_str}"
    elif diff_type == "候选名增加":
        added = ds_set - non_set
        return f"校正后新增了以下异构体: {';'.join(sorted(added))}"
    elif diff_type == "候选名改变":
        return f"校正后候选名发生增减/替换，移除了: {missing_str}"
    else:
        return ""

def main(input_csv, output_csv=None):
    if output_csv is None:
        output_csv = input_csv.replace(".csv", "_corrected.csv")
    
    df = pd.read_csv(input_csv, encoding="utf-8-sig")
    
    # 确保必要的列存在
    required = ["non_names", "ds_names", "mz_ds", "rt_ds"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"缺少列: {col}")
    
    new_diff_types = []
    new_missing_names = []
    new_reasons = []
    
    for idx, row in df.iterrows():
        diff_type, missing_str = correct_row(row)
        new_diff_types.append(diff_type)
        new_missing_names.append(missing_str)
        
        non_set = parse_name_set(row["non_names"])
        ds_set = parse_name_set(row["ds_names"])
        reason = generate_reason(diff_type, missing_str, non_set, ds_set)
        new_reasons.append(reason)
    
    # 更新列
    df["diff_type"] = new_diff_types
    df["missing_names"] = new_missing_names
    df["reason"] = new_reasons
    
    df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"修正完成，保存至: {output_csv}")

if __name__ == "__main__":
    # 用法：直接修改下面文件名，或通过命令行参数
    input_file = "metabolite_diff (2).csv"   # 替换为您的实际文件名
    output_file = "metabolite_diff_corrected.csv"
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        if len(sys.argv) > 2:
            output_file = sys.argv[2]
        else:
            output_file = input_file.replace(".csv", "_corrected.csv")
    
    main(input_file, output_file)
