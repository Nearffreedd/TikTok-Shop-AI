import os
import pandas as pd
import requests
import json
from datetime import datetime

# ================= 配置区 =================
API_KEY = "sk-63984c7bf8b041e48be89e8292ae24c6"  # <--- 在这里填入你新生成的 API Key
INPUT_FILE_NAME = "商品搜索_TT销量榜_20260525_135432.xlsx"  # <--- 确认文件名
OUTPUT_FILE_NAME = "选品分析报告_" + datetime.now().strftime("%Y%m%d") + ".md"

# DeepSeek API 地址
API_URL = "https://api.deepseek.com/chat/completions"

def read_excel_data(filepath):
    """读取Excel文件的前几行作为样本数据"""
    try:
        df = pd.read_excel(filepath)
        # 只取前20行数据进行分析，避免Token消耗过多
        # 如果列名是中文，直接保留；如果是英文，最好映射一下
        data_sample = df.head(20).to_markdown(index=False)
        columns = ", ".join(df.columns.tolist())
        return data_sample, columns
    except Exception as e:
        print(f"❌ 读取Excel失败: {e}")
        return None, None

def ask_ai_for_analysis(data_markdown, columns):
    """调用 DeepSeek API 进行分析"""
    print("🧠 正在思考并分析数据... (这可能需要几秒钟)")

    prompt = f"""
    你是一位资深的TikTok电商运营专家。
    我提供了一份TikTok商品销量榜的Excel数据样本（Markdown格式），包含列：[{columns}]。
    
    请根据这份数据，帮我写一份《本周选品分析报告》。
    报告需要包含以下内容：
    1. **爆款特征总结**：销量最高的商品有哪些共同点（价格区间、类目、功能）？
    2. **潜力黑马推荐**：找出3个销量不错但竞争可能较小的商品，并说明理由。
    3. **视频创作建议**：针对这些爆款，拍摄短视频时应该突出什么卖点？
    
    数据样本如下：
    {data_markdown}
    """

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    payload = {
        "model": "deepseek-chat",  # 使用 V3 或 V4 模型，取决于 DeepSeek 当前默认模型
        "messages": [
            {"role": "system", "content": "你是一个专业的电商数据分析师。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            return content
        else:
            print(f"❌ API调用失败: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"❌ 请求出错: {e}")
        return None

def main():
    # 1. 定位文件
    inbox_path = "0_Inbox"
    file_path = os.path.join(inbox_path, INPUT_FILE_NAME)

    if not os.path.exists(file_path):
        print(f"❌ 找不到文件: {file_path}")
        print("请检查文件名是否和 Inbox 文件夹里的一致。")
        return

    # 2. 读取数据
    data_md, cols = read_excel_data(file_path)
    if not data_md:
        return

    print(f"📊 已读取数据，共 {len(data_md.splitlines())} 行数据样本。")

    # 3. 调用AI
    report_content = ask_ai_for_analysis(data_md, cols)

    if report_content:
        # 4. 保存报告
        output_path = os.path.join(inbox_path, OUTPUT_FILE_NAME)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# TikTok 选品分析报告\n\n")
            f.write(f"> 基于文件：{INPUT_FILE_NAME}\n\n")
            f.write(f"---\n\n")
            f.write(report_content)
        
        print("-" * 30)
        print(f"✅ 分析完成！报告已生成：")
        print(f"📄 {output_path}")
        print("快去 Obsidian 里查看吧！")
        print("-" * 30)

if __name__ == "__main__":
    main()