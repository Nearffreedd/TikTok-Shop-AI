"""
TikTok 爆款视频分析专家 Agent
================================
功能：
  1. 上传视频 → 语音转文字（Whisper）→ 提取文案
  2. 分析视频脚本结构（钩子、痛点、解决方案、CTA）
  3. 存入爆款视频脚本库（Layer1_Permanent/05_Campaigns/Viral_Scripts/）
  4. 生成 1:1 复刻脚本 & 裂变脚本

用法：
  python scripts/viral_video_analyzer.py --upload <视频路径> [--product <产品名>] [--category <类目>]
  python scripts/viral_video_analyzer.py --list                    # 列出所有爆款脚本
  python scripts/viral_video_analyzer.py --view <脚本ID>           # 查看单个脚本详情
  python scripts/viral_video_analyzer.py --remix <脚本ID>          # 基于爆款脚本生成裂变版本
  python scripts/viral_video_analyzer.py --clone <脚本ID>          # 生成1:1复刻脚本
"""

import os
import sys
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

# ====== 路径配置 ======
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO_RAW_DIR = os.path.join(BASE_DIR, '0_Inbox', 'Video_Raw')
TRANSCRIPT_DIR = os.path.join(BASE_DIR, '0_Inbox', 'Temp_Transcripts')
VIRAL_SCRIPTS_DIR = os.path.join(BASE_DIR, 'Layer1_Permanent', '05_Campaigns', 'Viral_Scripts')
WORKING_DIR = os.path.join(BASE_DIR, 'Layer2_Working')

# 确保目录存在
for d in [VIDEO_RAW_DIR, TRANSCRIPT_DIR, VIRAL_SCRIPTS_DIR]:
    os.makedirs(d, exist_ok=True)

# 脚本库索引文件
SCRIPTS_INDEX = os.path.join(VIRAL_SCRIPTS_DIR, '_scripts_index.json')


# ============================================================
#  第一部分：语音转文字（Whisper 转录）
# ============================================================

def transcribe_video(video_path):
    """使用 faster-whisper 将视频语音转为文字"""
    filename = os.path.basename(video_path)
    name_no_ext = os.path.splitext(filename)[0]

    print(f"\n{'='*50}")
    print(f"[🎬] 开始转录视频: {filename}")
    print(f"{'='*50}")

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("[❌] 缺少 faster-whisper 库，请安装: pip install faster-whisper")
        print("[INFO] 将使用模拟模式（仅提取文件名信息）")
        return simulate_transcription(video_path)

    try:
        model = WhisperModel(
            "large-v3",
            device="cuda" if os.name != 'nt' else "cpu",
            compute_type="float16" if os.name != 'nt' else "int8"
        )

        segments, info = model.transcribe(
            video_path,
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False
        )

        full_text = ""
        segments_data = []
        for segment in segments:
            text = segment.text.strip()
            if text:
                segments_data.append({
                    'start': segment.start,
                    'end': segment.end,
                    'text': text
                })
                full_text += text + "\n"

        # 保存转录文本
        txt_path = os.path.join(TRANSCRIPT_DIR, f"{name_no_ext}.txt")
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(full_text)

        # 保存带时间戳的详细转录
        json_path = os.path.join(TRANSCRIPT_DIR, f"{name_no_ext}_segments.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(segments_data, f, ensure_ascii=False, indent=2)

        print(f"[✅] 转录完成！共 {len(segments_data)} 个片段")
        print(f"[📄] 文案保存至: {txt_path}")
        return full_text, segments_data

    except Exception as e:
        print(f"[❌] 转录失败: {e}")
        print("[INFO] 将使用模拟模式")
        return simulate_transcription(video_path)


def simulate_transcription(video_path):
    """模拟转录（当 Whisper 不可用时）"""
    filename = os.path.basename(video_path)
    name_no_ext = os.path.splitext(filename)[0]

    print(f"[⚠️] 模拟模式: 请手动提供视频文案")
    print(f"[💡] 将文案保存到 {TRANSCRIPT_DIR}/{name_no_ext}.txt 后重新运行")

    # 检查是否已有转录文件
    txt_path = os.path.join(TRANSCRIPT_DIR, f"{name_no_ext}.txt")
    if os.path.exists(txt_path):
        with open(txt_path, 'r', encoding='utf-8') as f:
            full_text = f.read()
        print(f"[📄] 发现已有转录文件: {txt_path}")
        return full_text, []

    return "", []


# ============================================================
#  第二部分：爆款视频脚本分析
# ============================================================

def analyze_video_script(transcript_text, segments=None, product_name="", category=""):
    """
    分析视频脚本结构，识别爆款元素
    返回结构化分析结果
    """
    print(f"\n{'='*50}")
    print(f"[🔍] 开始分析视频脚本结构...")
    print(f"{'='*50}")

    if not transcript_text.strip():
        print("[⚠️] 文案为空，无法分析")
        return None

    # 1. 提取关键信息
    lines = [l.strip() for l in transcript_text.split('\n') if l.strip()]
    total_words = len(transcript_text.split())
    estimated_duration = estimate_duration(total_words)

    # 2. 分析脚本结构
    structure = analyze_script_structure(transcript_text, lines)

    # 3. 提取卖点和关键词
    selling_points = extract_selling_points(transcript_text)

    # 4. 分析情感和语气
    tone_analysis = analyze_tone(transcript_text)

    # 5. 分析钩子效果
    hook_analysis = analyze_hook(lines[0] if lines else "")

    # 6. 生成结构化脚本
    script_analysis = {
        'basic_info': {
            'total_words': total_words,
            'estimated_duration_sec': estimated_duration,
            'total_lines': len(lines),
            'language': detect_language(transcript_text),
        },
        'hook_analysis': hook_analysis,
        'structure': structure,
        'selling_points': selling_points,
        'tone': tone_analysis,
        'full_transcript': transcript_text,
    }

    print(f"[✅] 分析完成！")
    print(f"    - 预估时长: {estimated_duration}秒")
    print(f"    - 脚本结构: {structure['pattern']}")
    print(f"    - 核心卖点: {len(selling_points)}个")
    print(f"    - 情感基调: {tone_analysis['primary_tone']}")

    return script_analysis


def estimate_duration(word_count):
    """根据字数估算视频时长（假设正常语速 150词/分钟）"""
    return max(15, int(word_count / 150 * 60))


def detect_language(text):
    """简单检测语言"""
    # 检查是否包含他加禄语常见词
    tagalog_markers = ['ang', 'ng', 'sa', 'ay', 'ko', 'mo', 'siya', 'kami', 'kayo',
                       'po', 'opo', 'salamat', 'mura', 'maganda', 'bago', 'sale',
                       'dito', 'diyan', 'ganito', 'ganyan']
    text_lower = text.lower()
    tagalog_count = sum(1 for word in tagalog_markers if word in text_lower)

    if tagalog_count >= 3:
        return "菲律宾语（他加禄语）"
    # 检查中文字符
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    if chinese_chars > 10:
        return "中文"
    return "英语"


def analyze_script_structure(text, lines):
    """分析脚本结构模式"""
    text_lower = text.lower()

    # 定义结构模式特征词
    patterns = {
        '痛点-解决方案': {
            'pain_keywords': ['problem', 'issue', 'sakit', 'hirap', 'nakakapagod',
                            'nakakainis', 'frustrated', 'struggle', 'ayaw', 'hassle'],
            'solution_keywords': ['try', 'solution', 'ito ang', 'dito', 'gamit',
                                'product', 'this is', 'effective', 'works']
        },
        '对比型': {
            'before_keywords': ['before', 'dati', 'noon', 'old way', 'traditional'],
            'after_keywords': ['after', 'ngayon', 'now', 'result', 'look at']
        },
        '教程/测评型': {
            'tutorial_keywords': ['step', 'first', 'second', 'next', 'then',
                                'gawin', 'paraan', 'how to', 'tips', 'tutorial']
        },
        '开箱型': {
            'unbox_keywords': ['unbox', 'open', 'package', 'delivery', 'arrived',
                             'dumating', 'box', 'first look']
        },
        '限时促销型': {
            'urgency_keywords': ['limited', 'sale', 'discount', 'promo', 'mura',
                               'bargain', 'today only', 'while', 'stock', 'offer',
                               'free shipping', 'voucher', 'code']
        }
    }

    # 检测匹配的模式
    matched_patterns = []
    for pattern_name, keywords in patterns.items():
        score = 0
        for category, kw_list in keywords.items():
            for kw in kw_list:
                if kw in text_lower:
                    score += 1
        if score >= 2:
            matched_patterns.append((pattern_name, score))

    # 排序，取最匹配的模式
    matched_patterns.sort(key=lambda x: x[1], reverse=True)

    # 分析时间线结构
    timeline = []
    if len(lines) >= 1:
        timeline.append(('0-3s', '钩子/开场', lines[0][:80]))
    if len(lines) >= 3:
        mid_start = max(1, len(lines) // 4)
        timeline.append(('3-15s', '问题/痛点展示', lines[mid_start][:80]))
    if len(lines) >= 5:
        mid = len(lines) // 2
        timeline.append(('15-30s', '产品解决方案', lines[mid][:80]))
    if len(lines) >= 7:
        timeline.append(('30-40s+', '行动呼吁(CTA)', lines[-1][:80]))

    return {
        'pattern': matched_patterns[0][0] if matched_patterns else '通用型',
        'pattern_confidence': matched_patterns[0][1] if matched_patterns else 0,
        'all_matched_patterns': [p[0] for p in matched_patterns],
        'timeline': timeline,
        'has_cta': any(kw in text_lower for kw in
                      ['shop', 'buy', 'order', 'check', 'link', 'bio', 'code',
                       'avail', 'grab', 'get yours', 'click', 'bilin', 'order na']),
        'has_urgency': any(kw in text_lower for kw in
                          ['limited', 'today', 'while', 'last', 'sale', 'mura'])
    }


def analyze_hook(first_line):
    """分析开场钩子"""
    if not first_line:
        return {'type': '未知', 'effectiveness': '低'}

    first_lower = first_line.lower()

    # 钩子类型识别
    hook_types = {
        '问题提问': ['what if', 'have you', 'do you', 'are you', 'did you',
                    'gusto mo', 'alam mo', 'sabi mo'],
        '惊人陈述': ['shocking', 'unbelievable', 'crazy', 'insane', 'wait',
                    'you won\'t believe', 'hindi ka maniniwala'],
        '数字/数据': [str(i) for i in range(10)] + ['percent', 'piso', 'pesos'],
        '直接对比': ['before', 'after', 'vs', 'compare', 'dati', 'noon', 'ngayon'],
        '好奇驱动': ['secret', 'hidden', 'nobody', 'never', 'always',
                    'the truth', 'real reason'],
        '利益承诺': ['free', 'save', 'earn', 'get', 'how to', 'paraan para']
    }

    detected_types = []
    for htype, keywords in hook_types.items():
        for kw in keywords:
            if kw in first_lower:
                detected_types.append(htype)
                break

    return {
        'text': first_line[:100],
        'type': detected_types[0] if detected_types else '通用开场',
        'all_types': detected_types,
        'length': len(first_line),
        'is_question': '?' in first_line,
        'has_emphasis': any(c in first_line for c in ['!', '🔥', '💥', '⚠️', '🎯'])
    }


def extract_selling_points(text):
    """提取核心卖点"""
    text_lower = text.lower()

    # 卖点关键词
    selling_signals = [
        ('价格优势', ['mura', 'cheap', 'affordable', 'budget', 'sulit', 'worth',
                    'tipid', 'save', 'discount', 'presyo']),
        ('质量优势', ['quality', 'premium', 'matibay', 'durable', 'high quality',
                    'solid', 'strong', 'best']),
        ('功能优势', ['feature', 'function', 'pwedeng', 'pwedeng gamitin',
                    'multi', 'versatile', 'practical']),
        ('外观优势', ['maganda', 'beautiful', 'cute', 'stylish', 'design',
                    'elegant', 'fashion', 'trendy', 'aesthetic']),
        ('使用便捷', ['easy', 'simple', 'dali', 'madali', 'convenient',
                    'quick', 'fast', 'instant']),
        ('赠品/优惠', ['free', 'bonus', 'gift', 'extra', 'included', 'libre']),
    ]

    selling_points = []
    for category, keywords in selling_signals:
        matched = [kw for kw in keywords if kw in text_lower]
        if matched:
            selling_points.append({
                'category': category,
                'matched_keywords': matched,
                'strength': len(matched)
            })

    selling_points.sort(key=lambda x: x['strength'], reverse=True)
    return selling_points


def analyze_tone(text):
    """分析情感和语气"""
    text_lower = text.lower()

    # 情感词汇
    tone_signals = {
        '兴奋/热情': ['amazing', 'awesome', 'incredible', 'wow', 'galing',
                    'sulit', 'super', 'sobrang', 'ang ganda'],
        '紧迫感': ['limited', 'hurry', 'last chance', 'while', 'today only',
                 'mabilis', 'bilis', 'konti na lang'],
        '专业/可信': ['guaranteed', 'warranty', 'trusted', 'legit', 'original',
                    'authentic', 'sure', 'guaranteed'],
        '亲切/日常': ['guys', 'friend', 'kayo', 'tayo', 'po', 'opal', 'mare',
                    'pre', 'besh'],
        '问题导向': ['problem', 'issue', 'sakit', 'hirap', 'nakakapagod',
                   'frustrated', 'ayaw']
    }

    detected_tones = []
    for tone, keywords in tone_signals.items():
        count = sum(1 for kw in keywords if kw in text_lower)
        if count > 0:
            detected_tones.append({'tone': tone, 'score': count})

    detected_tones.sort(key=lambda x: x['score'], reverse=True)

    return {
        'primary_tone': detected_tones[0]['tone'] if detected_tones else '中性',
        'all_tones': detected_tones,
        'has_urgency': any(kw in text_lower for kw in
                          ['limited', 'hurry', 'today', 'while stocks', 'mabilis']),
        'has_social_proof': any(kw in text_lower for kw in
                               ['viral', 'trending', 'sold', 'bestseller',
                                'popular', 'marami', 'sikat'])
    }


# ============================================================
#  第三部分：脚本库管理
# ============================================================

def load_scripts_index():
    """加载脚本库索引"""
    if os.path.exists(SCRIPTS_INDEX):
        with open(SCRIPTS_INDEX, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'scripts': [], 'categories': {}, 'last_update': None}


def save_scripts_index(index):
    """保存脚本库索引"""
    index['last_update'] = datetime.now().isoformat()
    os.makedirs(os.path.dirname(SCRIPTS_INDEX), exist_ok=True)
    with open(SCRIPTS_INDEX, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def find_script_by_id(index, script_id):
    """根据ID查找脚本"""
    for script in index['scripts']:
        if script['script_id'] == script_id:
            return script
    return None


def generate_script_id():
    """生成唯一脚本ID"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"VS_{timestamp}"


def save_viral_script(analysis, video_path="", product_name="", category=""):
    """将分析结果保存到爆款脚本库"""
    script_id = generate_script_id()
    filename = os.path.basename(video_path) if video_path else "manual_input"
    name_no_ext = os.path.splitext(filename)[0]

    # 构建脚本库条目
    script_entry = {
        'script_id': script_id,
        'created_at': datetime.now().isoformat(),
        'source_video': filename,
        'product_name': product_name or name_no_ext,
        'category': category or '未分类',
        'analysis': analysis,
        'tags': [],
        'remix_count': 0,
        'clone_count': 0,
    }

    # 自动生成标签
    if analysis:
        tags = []
        if analysis['structure']['pattern']:
            tags.append(analysis['structure']['pattern'])
        if analysis['hook_analysis']['type']:
            tags.append(f"钩子-{analysis['hook_analysis']['type']}")
        if analysis['tone']['primary_tone']:
            tags.append(f"语气-{analysis['tone']['primary_tone']}")
        if analysis['basic_info']['language']:
            tags.append(analysis['basic_info']['language'])
        if analysis['structure']['has_cta']:
            tags.append('有CTA')
        if analysis['structure']['has_urgency']:
            tags.append('紧迫感')
        script_entry['tags'] = tags

    # 保存到索引
    index = load_scripts_index()
    index['scripts'].append(script_entry)

    # 更新分类统计
    cat = script_entry['category']
    if cat not in index['categories']:
        index['categories'][cat] = []
    index['categories'][cat].append(script_id)

    save_scripts_index(index)

    # 同时生成 Markdown 文件到脚本库
    md_path = os.path.join(VIRAL_SCRIPTS_DIR, f"{script_id}_{name_no_ext}.md")
    md_content = generate_script_markdown(script_entry)
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)

    print(f"\n[✅] 爆款脚本已保存！")
    print(f"    📁 脚本ID: {script_id}")
    print(f"    📄 Markdown: {md_path}")
    print(f"    🏷️  标签: {', '.join(tags)}")

    return script_id, md_path


def generate_script_markdown(script_entry):
    """生成爆款脚本的 Markdown 文件"""
    a = script_entry.get('analysis', {})
    if not a:
        return f"# 爆款脚本: {script_entry['product_name']}\n\n（无分析数据）"

    md = f"""---
script_id: {script_entry['script_id']}
created_at: {script_entry['created_at']}
source_video: {script_entry['source_video']}
product: {script_entry['product_name']}
category: {script_entry['category']}
tags: [{', '.join(script_entry['tags'])}]
---

# 🎬 爆款视频脚本分析：{script_entry['product_name']}

## 📋 基本信息

| 项目 | 内容 |
| :--- | :--- |
| 脚本ID | `{script_entry['script_id']}` |
| 来源视频 | {script_entry['source_video']} |
| 产品名称 | {script_entry['product_name']} |
| 类目 | {script_entry['category']} |
| 分析时间 | {script_entry['created_at']} |
| 语言 | {a['basic_info']['language']} |
| 预估时长 | {a['basic_info']['estimated_duration_sec']}秒 |
| 总词数 | {a['basic_info']['total_words']}词 |

---

## 🎣 钩子分析（黄金前3秒）

| 维度 | 内容 |
| :--- | :--- |
| 钩子类型 | **{a['hook_analysis']['type']}** |
| 钩子文案 | `{a['hook_analysis']['text']}` |
| 是否为问句 | {'✅ 是' if a['hook_analysis']['is_question'] else '❌ 否'} |
| 是否有强调 | {'✅ 有' if a['hook_analysis']['has_emphasis'] else '❌ 无'} |

---

## 📐 脚本结构分析

**核心模式**: {a['structure']['pattern']}

### 时间线结构

| 时间段 | 环节 | 文案摘要 |
| :--- | :--- | :--- |
"""
    for time_range, stage, snippet in a['structure']['timeline']:
        md += f"| {time_range} | {stage} | {snippet} |\n"

    md += f"""
### 结构特征

- **有行动呼吁(CTA)**: {'✅' if a['structure']['has_cta'] else '❌'}
- **有紧迫感**: {'✅' if a['structure']['has_urgency'] else '❌'}
- **匹配模式**: {', '.join(a['structure']['all_matched_patterns'])}

---

## 💎 核心卖点提取

| 卖点类别 | 匹配关键词 | 强度 |
| :--- | :--- | :--- |
"""
    for sp in a['selling_points']:
        md += f"| {sp['category']} | {', '.join(sp['matched_keywords'])} | {'⭐' * sp['strength']} |\n"

    md += f"""
---

## 🎭 情感与语气分析

| 维度 | 内容 |
| :--- | :--- |
| 主要语气 | **{a['tone']['primary_tone']}** |
| 紧迫感 | {'✅ 有' if a['tone']['has_urgency'] else '❌ 无'} |
| 社交证明 | {'✅ 有' if a['tone']['has_social_proof'] else '❌ 无'} |

---

## 📝 完整文案

```
{a['full_transcript']}
```

---

## 🔄 复刻与裂变指南

### 1:1 复刻要点
- 保持 **{a['hook_analysis']['type']}** 类型的钩子开场
- 沿用 **{a['structure']['pattern']}** 的脚本结构
- 突出 **{', '.join([sp['category'] for sp in a['selling_points'][:3]])}** 等卖点
- 保持 **{a['tone']['primary_tone']}** 的语气风格

### 裂变方向建议
1. **换产品同结构**: 将本脚本结构套用到同品类其他产品
2. **换钩子类型**: 保持内容不变，替换开场钩子类型
3. **换语气风格**: 保持内容不变，调整语气（如从兴奋→专业）
4. **缩短版本**: 压缩到15-20秒用于广告投放
5. **延长版本**: 扩展到60秒+增加更多产品细节

---

*由 TikTok 爆款视频分析专家 Agent 自动生成*
"""
    return md


# ============================================================
#  第四部分：1:1 复刻 & 裂变脚本生成
# ============================================================

def generate_clone_script(script_id, new_product_name=""):
    """基于爆款脚本生成1:1复刻脚本"""
    index = load_scripts_index()
    script = find_script_by_id(index, script_id)

    if not script:
        print(f"[❌] 未找到脚本ID: {script_id}")
        return None

    a = script.get('analysis', {})
    if not a:
        print(f"[❌] 脚本 {script_id} 无分析数据")
        return None

    product = new_product_name or script['product_name']
    print(f"\n{'='*50}")
    print(f"[🔄] 生成 1:1 复刻脚本")
    print(f"    基于: {script['product_name']} ({script_id})")
    print(f"    新产品: {product}")
    print(f"{'='*50}")

    # 生成复刻脚本
    clone_script = f"""# 🎬 1:1 复刻脚本：{product}

> 基于爆款脚本 `{script_id}`（{script['product_name']}）复刻生成
> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 📋 脚本信息

| 项目 | 内容 |
| :--- | :--- |
| 产品 | {product} |
| 时长 | {a['basic_info']['estimated_duration_sec']}秒 |
| 风格 | {a['structure']['pattern']} |
| 语言 | {a['basic_info']['language']} |

## 🎬 分镜脚本

| 时间 | 画面内容 | 文案（语音） | 背景音乐 | 备注 |
| :--- | :--- | :--- | :--- | :--- |
"""
    # 根据原脚本结构生成分镜
    timeline = a['structure']['timeline']
    for i, (time_range, stage, snippet) in enumerate(timeline):
        bgm = "快节奏/悬念音效" if i == 0 else "情绪渲染" if i == 1 else "节奏加快" if i == 2 else "促销感BGM"
        note = "黄金前3秒" if i == 0 else "突出对比" if i == 2 else "挂车提醒" if i == 3 else ""
        clone_script += f"| {time_range} | [{stage}画面] | {snippet} | {bgm} | {note} |\n"

    clone_script += f"""
## 💡 复刻要点

1. **钩子**: 使用 **{a['hook_analysis']['type']}** 类型开场
2. **结构**: 沿用 **{a['structure']['pattern']}** 模式
3. **卖点**: 突出以下核心卖点
"""
    for sp in a['selling_points'][:3]:
        clone_script += f"   - {sp['category']}\n"

    clone_script += f"""
4. **语气**: 保持 **{a['tone']['primary_tone']}** 风格
5. **CTA**: {'必须包含行动呼吁' if a['structure']['has_cta'] else '建议加入行动呼吁'}

## 📝 原版文案参考

```
{a['full_transcript']}
```
"""

    # 保存复刻脚本
    output_path = os.path.join(WORKING_DIR, f"复刻脚本_{product}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(clone_script)

    # 更新复刻计数
    script['clone_count'] = script.get('clone_count', 0) + 1
    save_scripts_index(index)

    print(f"[✅] 复刻脚本已生成！")
    print(f"    📄 {output_path}")
    return output_path


def generate_remix_script(script_id, remix_type="structure", new_product_name=""):
    """
    基于爆款脚本生成裂变版本
    remix_type: structure(换产品同结构) | hook(换钩子) | tone(换语气) | short(缩短版) | long(延长版)
    """
    index = load_scripts_index()
    script = find_script_by_id(index, script_id)

    if not script:
        print(f"[❌] 未找到脚本ID: {script_id}")
        return None

    a = script.get('analysis', {})
    if not a:
        print(f"[❌] 脚本 {script_id} 无分析数据")
        return None

    product = new_product_name or script['product_name']
    print(f"\n{'='*50}")
    print(f"[🔄] 生成裂变脚本（{remix_type}）")
    print(f"    基于: {script['product_name']} ({script_id})")
    print(f"    新产品: {product}")
    print(f"{'='*50}")

    # 不同裂变类型的配置
    remix_configs = {
        'structure': {
            'title': '换产品同结构',
            'desc': '保持原脚本结构，替换为新产品卖点',
            'duration': a['basic_info']['estimated_duration_sec'],
        },
        'hook': {
            'title': '换钩子类型',
            'desc': '保持内容不变，替换开场钩子',
            'duration': a['basic_info']['estimated_duration_sec'],
        },
        'tone': {
            'title': '换语气风格',
            'desc': '保持内容不变，调整语气风格',
            'duration': a['basic_info']['estimated_duration_sec'],
        },
        'short': {
            'title': '缩短版（15-20秒）',
            'desc': '压缩脚本用于广告投放',
            'duration': 18,
        },
        'long': {
            'title': '延长版（60秒+）',
            'desc': '增加更多产品细节和展示',
            'duration': 60,
        },
    }

    config = remix_configs.get(remix_type, remix_configs['structure'])

    # 生成裂变脚本
    remix_script = f"""# 🎬 裂变脚本：{product}（{config['title']}）

> 基于爆款脚本 `{script_id}`（{script['product_name']}）裂变生成
> 裂变类型: {config['title']}
> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 📋 脚本信息

| 项目 | 内容 |
| :--- | :--- |
| 产品 | {product} |
| 时长 | {config['duration']}秒 |
| 裂变策略 | {config['desc']} |
| 语言 | {a['basic_info']['language']} |

## 🎬 分镜脚本

| 时间 | 画面内容 | 文案（语音） | 背景音乐 | 备注 |
| :--- | :--- | :--- | :--- | :--- |
"""
    # 根据裂变类型生成不同的分镜
    if remix_type == 'short':
        timeline_parts = [
            ('0-3s', '[钩子画面 - 快速吸引]', '[精简版开场]', '快节奏音效', '黄金前3秒'),
            ('3-12s', '[核心卖点展示]', '[精简版卖点]', '节奏加快', '突出核心卖点'),
            ('12-18s', '[CTA]', '[精简版行动呼吁]', '促销感BGM', '挂车提醒'),
        ]
    elif remix_type == 'long':
        timeline_parts = [
            ('0-3s', '[钩子画面]', '[开场吸引]', '快节奏/悬念音效', '黄金前3秒'),
            ('3-15s', '[问题展示]', '[用户痛点描述]', '情绪渲染', ''),
            ('15-35s', '[产品解决方案]', '[卖点+使用效果+细节展示]', '节奏加快', '突出对比'),
            ('35-50s', '[使用场景展示]', '[多场景应用]', '轻快BGM', '增加代入感'),
            ('50-60s', '[行动呼吁]', '[优惠+下单引导]', '促销感BGM', '挂车提醒'),
        ]
    elif remix_type == 'hook':
        hook_suggestions = {
            '问题提问': 'Are you tired of [痛点]?',
            '惊人陈述': "You won't believe what I just found!",
            '数字/数据': '₱99 lang, pero ang galing!',
            '直接对比': 'Before vs After — same product, different result!',
            '好奇驱动': 'The secret to [效果] that nobody tells you...',
            '利益承诺': 'How to get [好处] in just [时间]!',
        }
        new_hook = hook_suggestions.get(a['hook_analysis']['type'], 'Check this out!')
        timeline_parts = [
            ('0-3s', f'[新钩子画面 - 替换为{a["hook_analysis"]["type"]}型]', new_hook, '快节奏/悬念音效', '黄金前3秒'),
        ]
        for i, (time_range, stage, snippet) in enumerate(a['structure']['timeline'][1:], 1):
            timeline_parts.append((time_range, stage, snippet, '', ''))
    elif remix_type == 'tone':
        tone_swaps = {
            '兴奋/热情': '专业/可信',
            '专业/可信': '兴奋/热情',
            '紧迫感': '亲切/日常',
            '亲切/日常': '兴奋/热情',
            '问题导向': '专业/可信',
        }
        new_tone = tone_swaps.get(a['tone']['primary_tone'], '中性')
        timeline_parts = [
            ('0-3s', f'[钩子画面 - 语气调整为{new_tone}]', '[调整语气后的开场]', '快节奏/悬念音效', '黄金前3秒'),
        ]
        for i, (time_range, stage, snippet) in enumerate(a['structure']['timeline'][1:], 1):
            timeline_parts.append((time_range, stage, snippet, '', ''))
    else:
        # structure: 换产品同结构
        timeline_parts = []
        for i, (time_range, stage, snippet) in enumerate(a['structure']['timeline']):
            bgm = "快节奏/悬念音效" if i == 0 else "情绪渲染" if i == 1 else "节奏加快" if i == 2 else "促销感BGM"
            note = "黄金前3秒" if i == 0 else "突出对比" if i == 2 else "挂车提醒" if i == 3 else ""
            timeline_parts.append((time_range, f'[{stage}画面 - 替换为{product}展示]', snippet, bgm, note))

    # 写入分镜
    for time_range, scene, text, bgm, note in timeline_parts:
        remix_script += f"| {time_range} | {scene} | {text} | {bgm} | {note} |\n"

    remix_script += f"""
## 💡 裂变要点

- **裂变策略**: {config['desc']}
- **原脚本ID**: {script_id}
- **原产品**: {script['product_name']}

### 核心保留元素
1. **脚本结构**: 沿用 **{a['structure']['pattern']}** 模式
2. **核心卖点方向**: {', '.join([sp['category'] for sp in a['selling_points'][:3]])}
3. **CTA策略**: {'必须包含行动呼吁' if a['structure']['has_cta'] else '建议加入行动呼吁'}

## 📝 原版文案参考

```
{a['full_transcript']}
```
"""

    # 保存裂变脚本
    output_path = os.path.join(WORKING_DIR, f"裂变脚本_{product}_{remix_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(remix_script)

    # 更新裂变计数
    script['remix_count'] = script.get('remix_count', 0) + 1
    save_scripts_index(index)

    print(f"[✅] 裂变脚本已生成！")
    print(f"    📄 {output_path}")
    return output_path


# ============================================================
#  第五部分：脚本库浏览与管理
# ============================================================

def list_all_scripts():
    """列出所有爆款脚本"""
    index = load_scripts_index()
    scripts = index.get('scripts', [])

    if not scripts:
        print("\n[📭] 爆款脚本库为空")
        print("    💡 使用 --upload 上传视频开始分析")
        return

    print(f"\n{'='*60}")
    print(f"[📚] 爆款脚本库总览（共 {len(scripts)} 个脚本）")
    print(f"{'='*60}")
    print(f"{'ID':<25} {'产品':<20} {'类目':<12} {'结构模式':<16} {'复刻/裂变':<12}")
    print(f"{'-'*60}")

    for s in scripts:
        sid = s['script_id']
        product = s['product_name'][:18]
        cat = s['category'][:10]
        pattern = s.get('analysis', {}).get('structure', {}).get('pattern', '未知')[:14]
        counts = f"{s.get('clone_count',0)}/{s.get('remix_count',0)}"
        print(f"{sid:<25} {product:<20} {cat:<12} {pattern:<16} {counts:<12}")

    print(f"{'='*60}")
    print(f"[INFO] 使用 --view <脚本ID> 查看详情")
    print(f"[INFO] 使用 --clone <脚本ID> 生成复刻")
    print(f"[INFO] 使用 --remix <脚本ID> 生成裂变")

    # 按类目统计
    categories = index.get('categories', {})
    if categories:
        print(f"\n[📊] 按类目统计:")
        for cat, script_ids in sorted(categories.items()):
            print(f"    {cat}: {len(script_ids)} 个脚本")


def view_script_detail(script_id):
    """查看单个脚本详情"""
    index = load_scripts_index()
    script = find_script_by_id(index, script_id)

    if not script:
        print(f"[❌] 未找到脚本ID: {script_id}")
        return

    print(f"\n{'='*60}")
    print(f"[📄] 脚本详情: {script['product_name']}")
    print(f"{'='*60}")
    print(f"  ID:         {script['script_id']}")
    print(f"  产品:       {script['product_name']}")
    print(f"  类目:       {script['category']}")
    print(f"  来源视频:   {script['source_video']}")
    print(f"  创建时间:   {script['created_at']}")
    print(f"  标签:       {', '.join(script['tags'])}")
    print(f"  复刻次数:   {script.get('clone_count', 0)}")
    print(f"  裂变次数:   {script.get('remix_count', 0)}")

    a = script.get('analysis', {})
    if a:
        print(f"\n  📐 脚本结构: {a['structure']['pattern']}")
        print(f"  🎣 钩子类型: {a['hook_analysis']['type']}")
        print(f"  🎭 主要语气: {a['tone']['primary_tone']}")
        print(f"  🌐 语言:     {a['basic_info']['language']}")
        print(f"  ⏱️  预估时长: {a['basic_info']['estimated_duration_sec']}秒")
        print(f"  📝 总词数:   {a['basic_info']['total_words']}词")

        print(f"\n  💎 核心卖点:")
        for sp in a['selling_points'][:3]:
            print(f"    - {sp['category']} ({', '.join(sp['matched_keywords'])})")

        print(f"\n  📝 完整文案:")
        print(f"  {'='*40}")
        for line in a['full_transcript'].split('\n')[:10]:
            if line.strip():
                print(f"  {line.strip()}")
        if len(a['full_transcript'].split('\n')) > 10:
            print(f"  ...（共 {len(a['full_transcript'].split(chr(10)))} 行）")

    # 显示 Markdown 文件路径
    md_filename = f"{script_id}_{os.path.splitext(script['source_video'])[0]}.md"
    md_path = os.path.join(VIRAL_SCRIPTS_DIR, md_filename)
    if os.path.exists(md_path):
        print(f"\n  📄 Markdown: {md_path}")


# ============================================================
#  第六部分：CLI 主入口
# ============================================================

def print_banner():
    """打印启动横幅"""
    banner = """
╔══════════════════════════════════════════════════════╗
║     🎬 TikTok 爆款视频分析专家 Agent                ║
║     分析 · 入库 · 复刻 · 裂变                       ║
╚══════════════════════════════════════════════════════╝
"""
    print(banner)


def main():
    print_banner()

    if len(sys.argv) < 2:
        print("用法:")
        print("  python scripts/viral_video_analyzer.py --upload <视频路径> [--product <产品名>] [--category <类目>]")
        print("  python scripts/viral_video_analyzer.py --list")
        print("  python scripts/viral_video_analyzer.py --view <脚本ID>")
        print("  python scripts/viral_video_analyzer.py --clone <脚本ID> [--product <新产品名>]")
        print("  python scripts/viral_video_analyzer.py --remix <脚本ID> [--type <裂变类型>] [--product <新产品名>]")
        print("\n裂变类型: structure(换产品同结构) | hook(换钩子) | tone(换语气) | short(缩短版) | long(延长版)")
        return

    command = sys.argv[1]

    if command == '--upload':
        # 上传并分析视频
        if len(sys.argv) < 3:
            print("[❌] 请指定视频路径")
            return

        video_path = sys.argv[2]
        if not os.path.exists(video_path):
            print(f"[❌] 视频文件不存在: {video_path}")
            return

        # 解析可选参数
        product_name = ""
        category = ""
        for i, arg in enumerate(sys.argv):
            if arg == '--product' and i + 1 < len(sys.argv):
                product_name = sys.argv[i + 1]
            elif arg == '--category' and i + 1 < len(sys.argv):
                category = sys.argv[i + 1]

        # Step 1: 转录
        transcript, segments = transcribe_video(video_path)

        if not transcript.strip():
            print("[❌] 无法获取视频文案，请手动将文案保存到:")
            name_no_ext = os.path.splitext(os.path.basename(video_path))[0]
            print(f"    {TRANSCRIPT_DIR}/{name_no_ext}.txt")
            print("    然后重新运行此命令")
            return

        # Step 2: 分析
        analysis = analyze_video_script(transcript, segments, product_name, category)

        if not analysis:
            print("[❌] 分析失败")
            return

        # Step 3: 保存到脚本库
        script_id, md_path = save_viral_script(analysis, video_path, product_name, category)

        print(f"\n{'='*50}")
        print(f"[🎉] 爆款视频分析完成！")
        print(f"    📁 脚本ID: {script_id}")
        print(f"    📄 报告: {md_path}")
        print(f"{'='*50}")

    elif command == '--list':
        list_all_scripts()

    elif command == '--view':
        if len(sys.argv) < 3:
            print("[❌] 请指定脚本ID")
            return
        view_script_detail(sys.argv[2])

    elif command == '--clone':
        if len(sys.argv) < 3:
            print("[❌] 请指定脚本ID")
            return

        script_id = sys.argv[2]
        new_product = ""
        for i, arg in enumerate(sys.argv):
            if arg == '--product' and i + 1 < len(sys.argv):
                new_product = sys.argv[i + 1]

        generate_clone_script(script_id, new_product)

    elif command == '--remix':
        if len(sys.argv) < 3:
            print("[❌] 请指定脚本ID")
            return

        script_id = sys.argv[2]
        remix_type = "structure"
        new_product = ""

        for i, arg in enumerate(sys.argv):
            if arg == '--type' and i + 1 < len(sys.argv):
                remix_type = sys.argv[i + 1]
            elif arg == '--product' and i + 1 < len(sys.argv):
                new_product = sys.argv[i + 1]

        generate_remix_script(script_id, remix_type, new_product)

    else:
        print(f"[❌] 未知命令: {command}")
        print("使用 --help 查看帮助")


if __name__ == '__main__':
    main()
