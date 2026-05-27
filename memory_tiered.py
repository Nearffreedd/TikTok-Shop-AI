import os
import sys
import datetime

# 配置路径
INBOX_DIR = "0_Inbox"
ARCHIVE_DIR = "2_Archive"

def init_system():
    """初始化文件夹"""
    print("🤖 记忆系统已启动...")
    if not os.path.exists(INBOX_DIR):
        os.makedirs(INBOX_DIR)
    if not os.path.exists(ARCHIVE_DIR):
        os.makedirs(ARCHIVE_DIR)

def add_note(content):
    """添加笔记到收件箱"""
    # 生成带时间戳的文件名，防止覆盖
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # 简单的文件名清洗，防止特殊字符报错
    safe_content = content[:10].replace(":", " ").replace(" ", "_")
    filename = f"{timestamp}_{safe_content}.md"
    filepath = os.path.join(INBOX_DIR, filename)

    # 写入内容
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"---\n")
        f.write(f"created: {timestamp}\n")
        f.write(f"tags: tiktok, note\n")
        f.write(f"---\n\n")
        f.write(f"# {content}\n\n")
        f.write(f"> 记录时间: {datetime.datetime.now()}\n")

    print(f"📥 已存入收件箱: {filename}")

def list_notes():
    """列出收件箱所有文件"""
    files = os.listdir(INBOX_DIR)
    if not files:
        print("📭 收件箱是空的。")
        return

    print(f"--- 📂 收件箱文件列表 ({len(files)} 个) ---")
    for f in sorted(files, reverse=True): # 按最新排序
        print(f"- {f}")
    print("--------------------------------")

def search_notes(keyword):
    """在文件中搜索关键词"""
    files = os.listdir(INBOX_DIR)
    found = False
    print(f"🔍 正在搜索关键词: '{keyword}' ...")

    for f in files:
        filepath = os.path.join(INBOX_DIR, f)
        with open(filepath, "r", encoding="utf-8") as file:
            content = file.read()
            if keyword in content:
                print(f"✅ 在文件中找到: {f}")
                found = True

    if not found:
        print("❌ 未找到相关内容。")

# 主程序入口
if __name__ == "__main__":
    init_system()

    # 简单的命令行参数解析
    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "add" and len(sys.argv) > 2:
            # 拼接所有参数作为内容
            content = " ".join(sys.argv[2:])
            add_note(content)

        elif command == "list":
            list_notes()

        elif command == "search" and len(sys.argv) > 2:
            keyword = sys.argv[2]
            search_notes(keyword)

        else:
            print("⚠️ 用法: python memory_tiered.py [add/list/search] [内容]")
    else:
        print("⚠️ 请输入指令，例如: python memory_tiered.py add '测试内容'")