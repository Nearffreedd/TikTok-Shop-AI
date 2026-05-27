"""
📚 知识沉淀自动同步器 (Auto Knowledge Sync)
============================================
功能：解析复盘报告的"知识沉淀清单"，自动将未完成的知识更新项
      追加到对应的 SOP/知识库文件，并标记为已完成。

用法：
  python auto_knowledge_sync.py "Layer2_Working/复盘报告_周度_20260526.md"
  python auto_knowledge_sync.py --all    # 扫描所有复盘报告
  python auto_knowledge_sync.py --check  # 仅检查不做写入

依赖：无（纯Python标准库）
"""

import os
import re
import sys
import io
from datetime import datetime

# ====================== 编码修复 ======================
# 确保Windows GBK终端能正常输出Emoji和中文
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ====================== 路径配置 ======================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LAYER1_DIR = os.path.join(BASE_DIR, 'Layer1_Permanent')
LAYER2_DIR = os.path.join(BASE_DIR, 'Layer2_Working')
SOP_DIR = os.path.join(LAYER1_DIR, '06_Operations')

# ====================== 文件路径映射 ======================
# 将知识沉淀清单中的短路径名映射到实际文件路径
PATH_MAP = {
    "选品SOP.md": os.path.join(SOP_DIR, "选品SOP.md"),
    "商品数据分析SOP.md": os.path.join(SOP_DIR, "商品数据分析SOP.md"),
    "爆款视频分析SOP.md": os.path.join(SOP_DIR, "爆款视频分析SOP.md"),
    "广告SOP.md": os.path.join(LAYER1_DIR, "01_My_Shop", "广告SOP.md"),
    "避坑清单.md": os.path.join(SOP_DIR, "避坑清单.md"),
    "运营日志": os.path.join(LAYER2_DIR, "运营日志"),
}

# ====================== 内容模板 ======================
# 为不同类型的更新项提供格式化的追加内容
CONTENT_TEMPLATES = {
    "选品SOP.md": "\n\n---\n*📚 以下内容由 auto_knowledge_sync.py 于 {date} 自动追加*\n\n## {title}\n\n{content}\n",
    "商品数据分析SOP.md": "\n\n---\n*📚 以下内容由 auto_knowledge_sync.py 于 {date} 自动追加*\n\n## {title}\n\n{content}\n",
    "爆款视频分析SOP.md": "\n\n---\n*📚 以下内容由 auto_knowledge_sync.py 于 {date} 自动追加*\n\n## {title}\n\n{content}\n",
    "广告SOP.md": "\n\n---\n*📚 以下内容由 auto_knowledge_sync.py 于 {date} 自动追加*\n\n## {title}\n\n{content}\n",
    "避坑清单.md": "\n\n---\n*📚 以下内容由 auto_knowledge_sync.py 于 {date} 自动追加*\n\n### {title}\n\n{content}\n",
    "运营日志": "\n\n---\n*📚 由复盘报告自动触发的更新 于 {date}*\n\n## 运营习惯提示\n\n{content}\n",
}

DEFAULT_TEMPLATE = "\n\n---\n*📚 知识自动同步于 {date}*\n\n## {title}\n\n{content}\n"


def parse_knowledge_items(report_path):
    """
    解析复盘报告，提取知识沉淀清单中的未完成项
    
    Args:
        report_path: 复盘报告的文件路径
        
    Returns:
        list[dict]: [{"file_key": "选品SOP.md", "description": "xxx", "raw_line": "- [ ] 更新...", "line_index": 90}]
    """
    if not os.path.exists(report_path):
        print(f"❌ 文件不存在: {report_path}")
        return []
    
    with open(report_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.split('\n')
    
    # 定位"知识沉淀清单"章节
    section_start = None
    section_end = None
    
    for i, line in enumerate(lines):
        # 找到Section标题
        if '知识沉淀清单' in line and line.startswith('#'):
            section_start = i
    
    if section_start is None:
        print("  ⚠️ 未找到知识沉淀清单章节")
        return []
    
    # 找下一个同级别标题（即下一个 ## 或 --- ）
    for i in range(section_start + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith('## ') and '知识沉淀' not in stripped:
            section_end = i
            break
        if stripped.startswith('---') and '知识沉淀' not in lines[section_start]:
            section_end = i
            break
    
    if section_end is None:
        section_end = len(lines)
    
    # 提取清单项
    items = []
    for i in range(section_start + 1, section_end):
        line = lines[i]
        stripped = line.strip()
        
        # 匹配 "- [ ] 更新 `file` — desc" 或 "- [x] 更新 `file` — desc"
        match = re.match(r'-\s*\[([ x])\]\s*更新\s*`([^`]+)`\s*[—\-–]\s*(.+)', stripped)
        if match:
            status = match.group(1)  # " " or "x"
            file_key = match.group(2).strip()
            description = match.group(3).strip()
            
            items.append({
                "status": status,
                "file_key": file_key,
                "description": description,
                "raw_line": line,
                "line_index": i,
                "done": (status == 'x'),
            })
    
    return items


def generate_content(file_key, description):
    """
    根据更新描述自动生成要追加到文件的内容
    
    Args:
        file_key: 文件键名（如 "选品SOP.md"）
        description: 更新描述
        
    Returns:
        str: 格式化的Markdown内容
    """
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 从描述中提取标题和内容
    # 常见格式: "增加xxx章节" 或 "新增xxx条目"
    
    # 提取动作词
    action_match = re.match(r'(增加|新增|添加|更新|补充|修改|优化)(.+?)(章节|条目|维度|内容|部分)', description)
    if action_match:
        action = action_match.group(1)
        topic = action_match.group(2).strip()
        item_type = action_match.group(3)
        title = f"{action}{topic}_{item_type}"
    else:
        title = description[:30] + "..."
    
    # 生成内容
    template = CONTENT_TEMPLATES.get(file_key, DEFAULT_TEMPLATE)
    content = f"根据复盘报告({today})的建议：{description}\n\n> ⚠️ 此内容为自动生成占位符，请审阅后填充具体内容\n"
    
    return template.format(date=today, title=title, content=content)


def append_to_file(target_path, content, dry_run=False):
    """追加内容到目标文件"""
    if dry_run:
        # 如果是干运行，只返回将要追加的内容
        return True, content
    
    if not os.path.exists(os.path.dirname(target_path)):
        print(f"  ⚠️ 目录不存在，将创建: {os.path.dirname(target_path)}")
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
    
    with open(target_path, 'a', encoding='utf-8') as f:
        f.write(content)
    
    return True, None


def mark_item_done(report_path, line_index, dry_run=False):
    """在复盘报告中标记某个知识项为已完成（[ ] → [x]）"""
    if dry_run:
        return True
    
    with open(report_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    if line_index < len(lines):
        old_line = lines[line_index]
        new_line = old_line.replace('- [ ]', '- [x]', 1)
        if old_line != new_line:
            lines[line_index] = new_line
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            return True
    
    return False


def sync_knowledge(report_path, dry_run=False):
    """
    主函数：同步知识沉淀清单
    
    Returns:
        dict: 执行结果统计
    """
    print(f"\n{'='*50}")
    print(f"  📚 知识沉淀同步")
    print(f"  📄 报告: {report_path}")
    if dry_run:
        print(f"  🔍 模式: 仅检查（不写入）")
    print(f"{'='*50}\n")
    
    # Step 1: 解析清单
    items = parse_knowledge_items(report_path)
    if not items:
        print("  ❌ 未找到有效的知识沉淀项")
        return {"total": 0, "done_before": 0, "completed": 0, "skipped": 0, "errors": 0}
    
    print(f"  共找到 {len(items)} 条知识沉淀项:\n")
    for item in items:
        status_icon = "✅" if item["done"] else "⬜"
        print(f"    {status_icon} [{item['file_key']}] {item['description']}")
    
    pending = [i for i in items if not i["done"]]
    done_already = [i for i in items if i["done"]]
    
    print(f"\n  已完成: {len(done_already)} 项")
    print(f"  待处理: {len(pending)} 项\n")
    
    if not pending:
        print("  🎉 所有知识沉淀项已完成！")
        return {"total": len(items), "done_before": len(done_already), "completed": 0, "skipped": 0, "errors": 0}
    
    # Step 2: 执行更新
    completed = 0
    skipped = 0
    errors = 0
    
    for item in pending:
        file_key = item["file_key"]
        description = item["description"]
        
        print(f"  📝 处理: [{file_key}] {description}")
        
        # 查找目标文件
        target_path = PATH_MAP.get(file_key)
        if not target_path:
            # 尝试在SOP_DIR下查找
            possible_path = os.path.join(SOP_DIR, file_key)
            if os.path.exists(possible_path):
                target_path = possible_path
            else:
                print(f"    ⚠️ 未找到映射路径，跳过: {file_key}")
                skipped += 1
                continue
        
        # 生成内容 & 追加
        content = generate_content(file_key, description)
        success, generated = append_to_file(target_path, content, dry_run)
        
        if success:
            print(f"    ✅ 已{'检查' if dry_run else '追加'}内容到: {target_path}")
            
            # 标记为已完成
            if not dry_run:
                mark_done = mark_item_done(report_path, item["line_index"], dry_run)
                if mark_done:
                    print(f"    ✅ 已在报告中标记为已完成")
            
            completed += 1
        else:
            print(f"    ❌ 写入失败: {target_path}")
            errors += 1
    
    # Step 3: 输出摘要
    print(f"\n{'='*50}")
    print(f"  执行摘要:")
    print(f"   总项数:    {len(items)}")
    print(f"   已完成:    {len(done_already)}")
    print(f"   本次同步:  {completed}")
    print(f"   跳过:      {skipped}")
    print(f"   错误:      {errors}")
    print(f"{'='*50}\n")
    
    return {
        "total": len(items),
        "done_before": len(done_already),
        "completed": completed,
        "skipped": skipped,
        "errors": errors,
    }


def scan_all_reports(dry_run=False):
    """扫描所有复盘报告"""
    if not os.path.exists(LAYER2_DIR):
        print(f"❌ 目录不存在: {LAYER2_DIR}")
        return
    
    # 查找复盘报告
    report_files = []
    for f in os.listdir(LAYER2_DIR):
        if f.startswith("复盘报告_") and f.endswith(".md"):
            report_files.append(os.path.join(LAYER2_DIR, f))
    
    if not report_files:
        print(f"📭 未找到复盘报告")
        return
    
    print(f"📂 找到 {len(report_files)} 个复盘报告:")
    for rf in report_files:
        print(f"  • {os.path.relpath(rf, BASE_DIR)}")
    
    total_results = {"total": 0, "done_before": 0, "completed": 0, "skipped": 0, "errors": 0}
    for rf in report_files:
        result = sync_knowledge(rf, dry_run)
        for k in total_results:
            total_results[k] += result[k]
    
    print(f"\n{'='*50}")
    print(f"  全局统计:")
    print(f"   总项数:   {total_results['total']}")
    print(f"   已完成:   {total_results['done_before']}")
    print(f"   本次同步: {total_results['completed']}")
    print(f"   跳过:     {total_results['skipped']}")
    print(f"   错误:     {total_results['errors']}")
    print(f"{'='*50}")


# ====================== 主程序 ======================
if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--all":
            scan_all_reports(dry_run=False)
        elif arg == "--check":
            if len(sys.argv) > 2:
                sync_knowledge(sys.argv[2], dry_run=True)
            else:
                scan_all_reports(dry_run=True)
        else:
            # 指定文件路径
            report_path = arg
            if not os.path.isabs(report_path):
                report_path = os.path.join(BASE_DIR, report_path)
            sync_knowledge(report_path, dry_run=False)
    else:
        # 默认：提示用法
        print(__doc__)
