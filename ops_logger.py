"""
📋 TikTok Shop 运营日志助理 (Operations Logger)
================================================
功能：记录你的日常运营操作，自我学习，主动提醒

用法：
  python ops_logger.py                    # 交互式对话模式
  python ops_logger.py "今天更新了SL07的视频"  # 单次记录模式
  python ops_logger.py --summary           # 查看今日摘要
  python ops_logger.py --weekly            # 生成周度汇总
  python ops_logger.py --analyze           # 分析运营习惯
  python ops_logger.py --ask "SL07最近更新了吗"  # 查询历史

数据存储：
  Layer2_Working/运营日志/          — 每日日志文件
  Layer1_Permanent/01_My_Shop/ops_journal.json  — 结构化数据库
  Layer1_Permanent/06_Operations/运营周志/  — 周度归档
"""

import os
import sys
import re
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, Counter

# ====================== 路径配置 ======================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LAYER1_DIR = os.path.join(BASE_DIR, 'Layer1_Permanent')
LAYER2_DIR = os.path.join(BASE_DIR, 'Layer2_Working')
LOG_DIR = os.path.join(LAYER2_DIR, '运营日志')
ARCHIVE_DIR = os.path.join(LAYER1_DIR, '06_Operations', '运营周志')
JOURNAL_DB = os.path.join(LAYER1_DIR, '01_My_Shop', 'ops_journal.json')
PRODUCT_LIST_PATH = os.path.join(LAYER1_DIR, '02_Products', '产品款式总表.md')

# ====================== 操作类型定义 ======================
OPERATION_TYPES = {
    "视频更新": {
        "keywords": ["更新", "发布", "上传", "发到", "发了", "视频", "发视频"],
        "fields": ["产品", "视频账号", "视频ID", "关联脚本", "备注"],
        "emoji": "🎬",
        "template": "{产品} → {视频账号} → {视频ID}",
    },
    "折扣创建": {
        "keywords": ["折扣", "打折", "优惠", "off", "降价", "促销", "减价"],
        "fields": ["产品", "折扣力度", "开始时间", "结束时间", "折扣类型"],
        "emoji": "💰",
        "template": "{产品} {折扣力度} off ({开始时间}~{结束时间})",
    },
    "活动报名": {
        "keywords": ["活动", "报名", "大促", "参加", "活动报名", "提报"],
        "fields": ["活动名称", "报名时间", "参与商品", "活动类型"],
        "emoji": "📢",
        "template": "{活动名称} → {参与商品}",
    },
    "新品上架": {
        "keywords": ["上架", "上新", "新品", "新上", "发布产品", "新链接"],
        "fields": ["产品代码", "上架时间", "定价", "备注"],
        "emoji": "📦",
        "template": "{产品代码} 定价{定价}",
    },
    "广告操作": {
        "keywords": ["广告", "GMV", "投放", "预算", "出价", "广告组", "计划"],
        "fields": ["广告类型", "产品", "预算", "调整内容", "备注"],
        "emoji": "📢",
        "template": "{广告类型} → {产品} 预算{预算}",
    },
    "店铺设置": {
        "keywords": ["Banner", "banner", "装修", "店铺", "首页", "分类", "橱窗"],
        "fields": ["操作类型", "内容描述", "备注"],
        "emoji": "🏪",
        "template": "{操作类型}: {内容描述}",
    },
    "其他": {
        "keywords": [],
        "fields": ["操作描述", "备注"],
        "emoji": "📝",
        "template": "{操作描述}",
    },
}

# ====================== 产品代码映射 ======================
PRODUCT_CODES = {
    'EH01': 'EH01 耳环', 'EH02': 'EH02 耳环',
    'FQ01': 'FQ01 发圈',
    'HC01': 'HC01 耗材',
    'JZ03': 'JZ03 戒指', 'JZ04': 'JZ04 戒指',
    'MJ01': 'MJ01 墨镜',
    'PD01': 'PD01 皮袋',
    'PK01': 'PK01 包装袋',
    'SK01': 'SK01 钥匙扣', 'SK02': 'SK02 钥匙扣',
    'SL01': 'SL01 手链', 'SL02': 'SL02 手链', 'SL03': 'SL03 手链',
    'SL04': 'SL04 手链', 'SL05': 'SL05 手链', 'SL06': 'SL06 手链', 'SL07': 'SL07 手链',
    'ST01': 'ST01 饰品套装', 'ST02': 'ST02 饰品套装', 'ST03': 'ST03 饰品套装',
    'ST04': 'ST04 饰品套装', 'ST05': 'ST05 饰品套装', 'ST06': 'ST06 饰品套装',
    'XL01': 'XL01 项链', 'XL02': 'XL02 项链', 'XL03': 'XL03 项链',
    'ZH01': 'ZH01 纸盒',
}

# ====================== 运营日志助理 ======================
class OperationsLogger:
    def __init__(self):
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.today_file = os.path.join(LOG_DIR, f"运营日志_{datetime.now().strftime('%Y%m%d')}.md")
        self._ensure_dirs()
        self.journal = self._load_journal()
        self.learning_data = self._analyze_learning_data()

    def _ensure_dirs(self):
        """确保目录结构存在"""
        for d in [LOG_DIR, ARCHIVE_DIR]:
            os.makedirs(d, exist_ok=True)

    def _load_journal(self):
        """加载结构化操作数据库"""
        if os.path.exists(JOURNAL_DB):
            try:
                with open(JOURNAL_DB, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        return {"operations": [], "preferences": {}, "stats": {}}

    def _save_journal(self):
        """保存结构化操作数据库"""
        os.makedirs(os.path.dirname(JOURNAL_DB), exist_ok=True)
        with open(JOURNAL_DB, 'w', encoding='utf-8') as f:
            json.dump(self.journal, f, ensure_ascii=False, indent=2)

    def _load_today_log(self):
        """加载今日日志内容"""
        if os.path.exists(self.today_file):
            with open(self.today_file, 'r', encoding='utf-8') as f:
                return f.read()
        return None

    def _save_today_log(self, content):
        """保存今日日志"""
        os.makedirs(os.path.dirname(self.today_file), exist_ok=True)
        with open(self.today_file, 'w', encoding='utf-8') as f:
            f.write(content)

    def _append_to_today_log(self, entry_md):
        """追加一条记录到今日日志"""
        existing = self._load_today_log()
        if existing:
            # 在最后一条记录前插入（在 --- 分隔符之前）
            if existing.rstrip().endswith('---'):
                content = existing.rstrip()[:-3].rstrip() + f"\n\n{entry_md}\n\n---\n"
            else:
                content = existing.rstrip() + f"\n\n{entry_md}\n\n---\n"
        else:
            content = self._generate_log_header() + f"\n\n{entry_md}\n\n---\n"
        self._save_today_log(content)

    def _generate_log_header(self):
        """生成日志文件头"""
        return f"""# 📋 运营日志 — {self.today}

> 自动记录我的日常运营操作

## 今日操作记录

"""

    # ====================== 意图识别 ======================
    def _detect_operation_type(self, text):
        """识别操作类型"""
        text_lower = text.lower()
        
        # 按优先级匹配
        for op_type, config in OPERATION_TYPES.items():
            if op_type == "其他":
                continue
            for keyword in config["keywords"]:
                if keyword.lower() in text_lower:
                    return op_type
        
        return "其他"

    def _extract_product(self, text):
        """从文本中提取产品代码"""
        text_upper = text.upper()
        for code in sorted(PRODUCT_CODES.keys(), key=len, reverse=True):
            if code in text_upper:
                return code
        return None

    def _extract_video_account(self, text):
        """提取视频账号"""
        # 匹配常见账号模式
        patterns = [
            r'账号\s*([A-Za-z0-9_\u4e00-\u9fa5]+)',
            r'发到\s*([A-Za-z0-9_\u4e00-\u9fa5]+)',
            r'([A-Za-z0-9_]+(?:账号|号))',
            r'(?:tiktok|tt)[_\s]?[A-Za-z0-9_]+',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None

    def _extract_video_id(self, text):
        """提取视频ID"""
        patterns = [
            r'视频ID[=:：]?\s*([A-Za-z0-9_]+)',
            r'ID[=:：]?\s*([A-Za-z0-9_]{6,})',
            r'v[=_]\s*([A-Za-z0-9]+)',
            r'video[=_]\s*([A-Za-z0-9]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None

    def _extract_discount(self, text):
        """提取折扣力度"""
        patterns = [
            r'(\d+)\s*%',
            r'(\d+)\s*折',
            r'off',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                val = match.group(1) if match.lastindex else "未知"
                return f"{val}%"
        return None

    def _extract_price(self, text):
        """提取价格"""
        patterns = [
            r'[₱Pp]?\s*(\d+(?:\.\d+)?)\s*(?:比索|peso)?',
            r'定价\s*(\d+(?:\.\d+)?)',
            r'售价\s*(\d+(?:\.\d+)?)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None

    def _extract_script(self, text):
        """提取脚本信息"""
        patterns = [
            r'脚本[=:：]?\s*([A-Za-z0-9_\u4e00-\u9fa5]+)',
            r'使用\s*([A-Za-z0-9_\u4e00-\u9fa5]+(?:脚本|版本))',
            r'([A-Za-z0-9_\u4e00-\u9fa5]+(?:脚本|版本|V\d+))',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None

    def _extract_activity_name(self, text):
        """提取活动名称"""
        patterns = [
            r'(?:报名|参加|提报)[了]?\s*([A-Za-z0-9_\u4e00-\u9fa5.]+(?:大促|活动|促销|节))',
            r'([A-Za-z0-9_\u4e00-\u9fa5.]+(?:大促|活动|促销|节))',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None

    def _extract_ad_type(self, text):
        """提取广告类型"""
        patterns = [
            r'(GMV\s*Max|GMVMAX|商品卡|直播|视频|搜索)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                return match.group(1)
        return None

    def _extract_budget(self, text):
        """提取预算"""
        patterns = [
            r'预算[=:：]?\s*[₱Pp]?\s*(\d+(?:\.\d+)?)',
            r'[₱Pp]\s*(\d+(?:\.\d+)?)\s*(?:预算|每天|每日)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return f"₱{match.group(1)}"
        return None

    def _extract_time_range(self, text):
        """提取时间范围"""
        patterns = [
            r'(?:到|至|~|—)\s*(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)',
            r'(?:到|至|~|—)\s*(月底|下月|下周)',
            r'(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)\s*(?:到|至|~|—)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None

    # ====================== 结构化解析 ======================
    def _parse_operation(self, text, op_type):
        """将自然语言解析为结构化操作记录"""
        record = {
            "type": op_type,
            "raw_text": text,
            "timestamp": datetime.now().isoformat(),
            "date": self.today,
        }

        # 通用提取
        product = self._extract_product(text)
        if product:
            record["产品"] = product

        # 按类型提取
        if op_type == "视频更新":
            record["视频账号"] = self._extract_video_account(text) or "未知账号"
            record["视频ID"] = self._extract_video_id(text) or "未知ID"
            script = self._extract_script(text)
            if script:
                record["关联脚本"] = script

        elif op_type == "折扣创建":
            record["折扣力度"] = self._extract_discount(text) or "未知"
            time_range = self._extract_time_range(text)
            if time_range:
                record["结束时间"] = time_range
            record["开始时间"] = self.today

        elif op_type == "活动报名":
            record["活动名称"] = self._extract_activity_name(text) or "未知活动"
            record["报名时间"] = self.today

        elif op_type == "新品上架":
            record["定价"] = self._extract_price(text) or "未知"
            record["上架时间"] = self.today

        elif op_type == "广告操作":
            record["广告类型"] = self._extract_ad_type(text) or "未知"
            budget = self._extract_budget(text)
            if budget:
                record["预算"] = budget

        elif op_type == "店铺设置":
            record["操作类型"] = "店铺装修"
            record["内容描述"] = text

        return record

    # ====================== 格式化输出 ======================
    def _format_record_md(self, record):
        """将结构化记录格式化为Markdown"""
        op_type = record["type"]
        config = OPERATION_TYPES.get(op_type, OPERATION_TYPES["其他"])
        emoji = config["emoji"]
        
        lines = [f"### {emoji} {op_type}"]
        lines.append(f"- **时间**: {record.get('timestamp', self.today)}")
        
        # 按字段顺序输出
        for field in config["fields"]:
            if field in record and record[field]:
                lines.append(f"- **{field}**: {record[field]}")
        
        # 原始文本
        lines.append(f"- **原始描述**: {record['raw_text']}")
        
        return "\n".join(lines)

    def _format_record_short(self, record):
        """简短格式（用于对话回复）"""
        op_type = record["type"]
        config = OPERATION_TYPES.get(op_type, OPERATION_TYPES["其他"])
        emoji = config["emoji"]
        
        parts = [f"{emoji} **{op_type}**"]
        for field in config["fields"]:
            if field in record and record[field]:
                parts.append(f"  {field}: {record[field]}")
        
        return "\n".join(parts)

    # ====================== 智能分析引擎 ======================
    def _analyze_learning_data(self):
        """分析历史数据，提取学习信息"""
        ops = self.journal.get("operations", [])
        if not ops:
            return {
                "product_frequency": {},
                "account_frequency": {},
                "discount_history": {},
                "operation_time_distribution": {},
                "weekly_pattern": {},
                "total_operations": 0,
                "last_operation_date": None,
            }

        # 产品操作频率
        product_freq = Counter()
        account_freq = Counter()
        discount_history = defaultdict(list)
        hourly_dist = Counter()
        weekly_dist = Counter()

        for op in ops:
            if "产品" in op:
                product_freq[op["产品"]] += 1
            if "视频账号" in op:
                account_freq[op["视频账号"]] += 1
            if op["type"] == "折扣创建" and "折扣力度" in op:
                product = op.get("产品", "未知")
                discount_history[product].append(op["折扣力度"])
            
            # 时间分布
            try:
                ts = datetime.fromisoformat(op["timestamp"])
                hourly_dist[ts.hour] += 1
                weekly_dist[ts.weekday()] += 1
            except (ValueError, KeyError):
                pass

        return {
            "product_frequency": dict(product_freq.most_common()),
            "account_frequency": dict(account_freq.most_common()),
            "discount_history": {k: list(v) for k, v in discount_history.items()},
            "operation_time_distribution": dict(hourly_dist),
            "weekly_pattern": dict(weekly_dist),
            "total_operations": len(ops),
            "last_operation_date": ops[-1].get("date") if ops else None,
        }

    def _get_learning_insights(self, record):
        """基于学习数据生成智能洞察"""
        insights = []
        learning = self.learning_data
        op_type = record["type"]
        product = record.get("产品")

        # 1. 频率分析
        if product and product in learning["product_frequency"]:
            count = learning["product_frequency"][product]
            if count >= 5:
                insights.append(f"💡 {product} 是你最常操作的产品之一（共{count}次）")
            elif count == 1:
                insights.append(f"💡 这是你第一次操作 {product}，需要我特别关注吗？")

        # 2. 账号偏好
        account = record.get("视频账号")
        if account and account in learning["account_frequency"]:
            count = learning["account_frequency"][account]
            insights.append(f"💡 你在 {account} 上已操作过 {count} 次")

        # 3. 折扣异常检测
        if op_type == "折扣创建" and product:
            discount = record.get("折扣力度")
            if discount and product in learning["discount_history"]:
                history = learning["discount_history"][product]
                if history:
                    # 简单异常检测：如果折扣力度与历史平均差异较大
                    try:
                        current_val = int(discount.replace('%', ''))
                        avg_val = sum(int(h.replace('%', '')) for h in history) / len(history)
                        if abs(current_val - avg_val) > 15:
                            insights.append(f"⚠️ **异常提醒**：你给 {product} 打了 {discount} off，历史平均约 {avg_val:.0f}%，确认无误？")
                        else:
                            insights.append(f"💡 你给 {product} 的折扣力度与历史习惯一致（平均 {avg_val:.0f}%）")
                    except ValueError:
                        pass

        # 4. 操作节奏
        if learning["total_operations"] > 10:
            # 周分布
            weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            if learning["weekly_pattern"]:
                peak_day = max(learning["weekly_pattern"], key=learning["weekly_pattern"].get)
                insights.append(f"💡 你通常在 {weekday_names[peak_day]} 操作最频繁")

        # 5. 长时间未操作提醒
        if product:
            # 检查该产品上次操作时间
            for op in reversed(self.journal.get("operations", [])):
                if op.get("产品") == product and op["type"] != op_type:
                    last_date = op.get("date")
                    if last_date:
                        try:
                            days_diff = (datetime.now() - datetime.strptime(last_date, "%Y-%m-%d")).days
                            if days_diff > 14:
                                insights.append(f"⏰ **提醒**：{product} 已经 {days_diff} 天没有操作了，建议关注")
                            elif days_diff > 7:
                                insights.append(f"💡 {product} 上次操作是 {days_diff} 天前")
                        except ValueError:
                            pass
                    break

        return insights

    # ====================== 核心处理逻辑 ======================
    def process(self, text):
        """处理一条运营操作记录"""
        # 1. 识别操作类型
        op_type = self._detect_operation_type(text)
        
        # 2. 结构化解析
        record = self._parse_operation(text, op_type)
        
        # 3. 保存到日志文件
        record_md = self._format_record_md(record)
        self._append_to_today_log(record_md)
        
        # 4. 保存到结构化数据库
        self.journal["operations"].append(record)
        self._save_journal()
        
        # 5. 更新学习数据
        self.learning_data = self._analyze_learning_data()
        
        # 6. 生成智能洞察
        insights = self._get_learning_insights(record)
        
        # 7. 返回结果
        return record, insights

    # ====================== 查询功能 ======================
    def query(self, question):
        """查询历史操作记录"""
        ops = self.journal.get("operations", [])
        if not ops:
            return "📭 还没有任何操作记录"

        question_lower = question.lower()
        results = []

        # 按产品查询
        product = self._extract_product(question)
        if product:
            results = [op for op in ops if op.get("产品") == product]
            if results:
                lines = [f"📋 **{product} 的操作历史**（共 {len(results)} 条）:\n"]
                for op in reversed(results[-10:]):  # 最近10条
                    lines.append(f"- {op['date']} {OPERATION_TYPES.get(op['type'], {}).get('emoji', '📝')} {op['type']}: {op.get('raw_text', '')}")
                return "\n".join(lines)

        # 按操作类型查询
        for op_type, config in OPERATION_TYPES.items():
            if op_type == "其他":
                continue
            for keyword in config["keywords"]:
                if keyword.lower() in question_lower:
                    results = [op for op in ops if op["type"] == op_type]
                    if results:
                        lines = [f"📋 **{op_type} 记录**（共 {len(results)} 条）:\n"]
                        for op in reversed(results[-10:]):
                            lines.append(f"- {op['date']}: {op.get('raw_text', '')}")
                        return "\n".join(lines)
                    else:
                        return f"📭 还没有 {op_type} 的记录"

        # 按日期查询
        date_pattern = re.search(r'(\d{4}[-/]?\d{1,2}[-/]?\d{1,2})', question)
        if date_pattern:
            date_str = date_pattern.group(1).replace('/', '-')
            results = [op for op in ops if op.get("date") == date_str]
            if results:
                lines = [f"📋 **{date_str} 的操作记录**（共 {len(results)} 条）:\n"]
                for op in results:
                    lines.append(f"- {OPERATION_TYPES.get(op['type'], {}).get('emoji', '📝')} {op['type']}: {op.get('raw_text', '')}")
                return "\n".join(lines)

        # 最近操作
        if "最近" in question_lower or "最新" in question_lower or "今天" in question_lower:
            today_ops = [op for op in ops if op.get("date") == self.today]
            if today_ops:
                lines = [f"📋 **今日操作记录**（共 {len(today_ops)} 条）:\n"]
                for op in today_ops:
                    lines.append(f"- {OPERATION_TYPES.get(op['type'], {}).get('emoji', '📝')} {op['type']}: {op.get('raw_text', '')}")
                return "\n".join(lines)
            else:
                return "📭 今天还没有操作记录"

        # 默认：返回最近5条
        recent = ops[-5:]
        lines = ["📋 **最近5条操作记录**:\n"]
        for op in reversed(recent):
            lines.append(f"- {op['date']} {OPERATION_TYPES.get(op['type'], {}).get('emoji', '📝')} {op['type']}: {op.get('raw_text', '')}")
        return "\n".join(lines)

    # ====================== 汇总功能 ======================
    def today_summary(self):
        """生成今日摘要"""
        ops = self.journal.get("operations", [])
        today_ops = [op for op in ops if op.get("date") == self.today]
        
        if not today_ops:
            return "📭 今天还没有任何操作记录"

        # 按类型统计
        type_count = Counter(op["type"] for op in today_ops)
        
        lines = [f"## 📊 今日运营摘要 — {self.today}\n"]
        lines.append(f"**总操作数**: {len(today_ops)} 条\n")
        lines.append("| 操作类型 | 数量 |")
        lines.append("|:---|:---:|")
        for op_type, count in type_count.most_common():
            emoji = OPERATION_TYPES.get(op_type, {}).get("emoji", "📝")
            lines.append(f"| {emoji} {op_type} | {count} |")
        
        lines.append("\n### 详细记录\n")
        for op in today_ops:
            lines.append(self._format_record_md(op))
            lines.append("")
        
        return "\n".join(lines)

    def weekly_summary(self):
        """生成周度汇总"""
        ops = self.journal.get("operations", [])
        if not ops:
            return "📭 还没有任何操作记录"

        # 计算本周范围（周一~周日）
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        
        week_ops = []
        for op in ops:
            try:
                op_date = datetime.strptime(op.get("date", ""), "%Y-%m-%d")
                if monday <= op_date <= sunday:
                    week_ops.append(op)
            except ValueError:
                continue

        if not week_ops:
            return f"📭 本周（{monday.strftime('%m/%d')}~{sunday.strftime('%m/%d')}）还没有操作记录"

        # 统计分析
        type_count = Counter(op["type"] for op in week_ops)
        product_count = Counter(op.get("产品") for op in week_ops if "产品" in op)
        
        lines = [f"## 📊 周度运营汇总 — {monday.strftime('%m/%d')}~{sunday.strftime('%m/%d')}\n"]
        lines.append(f"**本周总操作数**: {len(week_ops)} 条\n")
        
        lines.append("### 操作分布\n")
        lines.append("| 操作类型 | 数量 |")
        lines.append("|:---|:---:|")
        for op_type, count in type_count.most_common():
            emoji = OPERATION_TYPES.get(op_type, {}).get("emoji", "📝")
            lines.append(f"| {emoji} {op_type} | {count} |")
        
        if product_count:
            lines.append("\n### 活跃产品 Top 5\n")
            lines.append("| 产品 | 操作次数 |")
            lines.append("|:---|:---:|")
            for prod, count in product_count.most_common(5):
                if prod:
                    lines.append(f"| {prod} | {count} |")
        
        lines.append("\n### 详细记录\n")
        for op in week_ops:
            lines.append(self._format_record_md(op))
            lines.append("")
        
        # 保存周报
        week_str = monday.strftime("%Y%m%d")
        report_path = os.path.join(ARCHIVE_DIR, f"运营周志_{week_str}.md")
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        
        lines.append(f"\n📄 周报已保存: {report_path}")
        
        return "\n".join(lines)

    def analyze_habits(self):
        """分析运营习惯"""
        learning = self.learning_data
        ops = self.journal.get("operations", [])
        
        if not ops:
            return "📭 数据不足，请先记录一些操作后再来分析"

        lines = ["## 📈 运营习惯分析\n"]
        
        # 总体统计
        lines.append(f"**总操作数**: {learning['total_operations']} 条")
        lines.append(f"**首次记录**: {ops[0].get('date', '未知')}")
        lines.append(f"**最近记录**: {ops[-1].get('date', '未知')}\n")
        
        # 产品活跃度
        if learning["product_frequency"]:
            lines.append("### 🏷️ 产品活跃度\n")
            lines.append("| 产品 | 操作次数 | 占比 |")
            lines.append("|:---|:---:|:---:|")
            total = sum(learning["product_frequency"].values())
            for prod, count in list(learning["product_frequency"].items())[:10]:
                pct = count / total * 100
                lines.append(f"| {prod} | {count} | {pct:.1f}% |")
            lines.append("")
        
        # 账号偏好
        if learning["account_frequency"]:
            lines.append("### 📱 视频账号偏好\n")
            for acc, count in learning["account_frequency"].items():
                lines.append(f"- **{acc}**: {count} 次操作")
            lines.append("")
        
        # 时间分布
        if learning["weekly_pattern"]:
            lines.append("### 📅 周操作节奏\n")
            weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            for day in range(7):
                count = learning["weekly_pattern"].get(day, 0)
                bar = "█" * count + "░" * max(0, 10 - count)
                lines.append(f"- {weekday_names[day]}: {bar} {count}次")
            lines.append("")
        
        # 折扣习惯
        if learning["discount_history"]:
            lines.append("### 💰 折扣习惯\n")
            for prod, discounts in learning["discount_history"].items():
                if discounts:
                    try:
                        vals = [int(d.replace('%', '')) for d in discounts]
                        avg = sum(vals) / len(vals)
                        lines.append(f"- **{prod}**: 平均 {avg:.0f}% off，共 {len(vals)} 次")
                    except ValueError:
                        lines.append(f"- **{prod}**: {', '.join(discounts)}")
            lines.append("")
        
        # 建议
        lines.append("### 💡 优化建议\n")
        
        # 运营节奏建议（基于复盘经验：周中重推、周末维护）
        if learning["weekly_pattern"]:
            weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            # 计算周中（周一~周四）vs 周末（周五~周日）的操作分布
            midweek_ops = sum(learning["weekly_pattern"].get(d, 0) for d in [0, 1, 2, 3])  # 周一~周四
            weekend_ops = sum(learning["weekly_pattern"].get(d, 0) for d in [4, 5, 6])     # 周五~周日
            total_ops = midweek_ops + weekend_ops
            if total_ops > 0:
                midweek_pct = midweek_ops / total_ops * 100
                lines.append(f"- 📅 **运营节奏分析**：你周中（周一~周四）操作占比 {midweek_pct:.0f}%，周末占比 {100-midweek_pct:.0f}%")
                if midweek_pct < 60:
                    lines.append("  - 💡 **建议**：根据复盘经验，周三周四是黄金转化时段（转化率5.56%-6.59%），建议将重点推广活动集中在周二~周四发布，周五~周日安排轻量维护")
                else:
                    lines.append('  - ✅ **节奏良好**：你的操作节奏符合"周中重推、周末维护"的最佳实践')
        
        # 检查是否有长时间未操作的产品
        active_products = set()
        for op in reversed(ops):
            if "产品" in op:
                active_products.add(op["产品"])
                if len(active_products) >= 3:
                    break
        
        # 检查产品库中是否有从未操作过的产品
        all_products = set(PRODUCT_CODES.keys())
        operated_products = set(learning["product_frequency"].keys())
        untouched = all_products - operated_products
        if untouched:
            lines.append(f"- 📦 你有 {len(untouched)} 个产品从未记录过操作: {', '.join(list(untouched)[:5])}...")
        
        # 操作频率建议
        if learning["total_operations"] < 10:
            lines.append("- 📝 记录还不多，坚持每天记录，我会越来越懂你的运营习惯")
        elif learning["total_operations"] > 50:
            lines.append("- 🎯 你已经积累了丰富的操作数据，可以考虑将高频操作固化为SOP")
        
        if not lines[-1].startswith("-"):
            lines.append("- ✅ 运营节奏良好，继续保持！")
        
        return "\n".join(lines)

    # ====================== 交互式对话 ======================
    def interactive(self):
        """交互式对话模式"""
        print(r"""
╔══════════════════════════════════════════════════╗
║     📋 TikTok Shop 运营日志助理 已就位            ║
║                                                  ║
║  你可以这样告诉我：                                ║
║  • "今天把SL07的视频发到了账号A，ID是abc123"      ║
║  • "给SL06和ST01各设置了20% off，到月底"          ║
║  • "报名了TikTok 6.6大促，报了SL06和ST01"         ║
║  • "上架了SL08，定价₱99"                          ║
║  • "给SL07创建了GMV Max广告，预算₱500"            ║
║                                                  ║
║  查询命令：                                       ║
║  • "今天做了什么" — 查看今日记录                  ║
║  • "SL07最近更新了吗" — 查询产品操作历史          ║
║  • "最近有什么操作" — 查看最近5条记录             ║
║  • "分析我的习惯" — 查看运营习惯分析              ║
║  • "周报" — 生成周度汇总                         ║
║  • "帮助" — 查看完整指令清单                     ║
║  • "退出" — 退出                                 ║
╚══════════════════════════════════════════════════╝
""")
        
        while True:
            try:
                user_input = input("\n💬 你: ").strip()
                if user_input.lower() in ["退出", "exit", "quit"]:
                    print("👋 再见！")
                    break
                elif user_input.lower() in ["帮助", "help", "?"]:
                    self._show_interactive_help()
                elif user_input.lower() in ["今天做了什么", "今日", "今天", "--summary"]:
                    print("\n" + self.today_summary())
                elif user_input.lower() in ["周报", "周度", "--weekly", "weekly"]:
                    print("\n" + self.weekly_summary())
                elif user_input.lower() in ["分析我的习惯", "习惯分析", "学习", "--analyze", "analyze"]:
                    print("\n" + self.analyze_habits())
                elif user_input.lower().startswith(("ask ", "查询", "查", "?")):
                    query_text = re.sub(r'^(ask|查询|查|\?)\s*', '', user_input, flags=re.I)
                    print("\n" + self.query(query_text))
                elif user_input:
                    # 当作操作记录处理
                    record, insights = self.process(user_input)
                    print(f"\n✅ **已记录！**\n")
                    print(self._format_record_short(record))
                    if insights:
                        print("")
                        for insight in insights:
                            print(insight)
                else:
                    continue
                    
            except KeyboardInterrupt:
                print("\n👋 再见！")
                break
            except EOFError:
                break

    def _show_interactive_help(self):
        """显示交互式帮助信息"""
        print("""
📋 **指令清单**
═══════════════════════════════════════

📝 **记录操作**（直接说就行）
  • "今天把SL07的视频发到了账号A，ID是abc123"
  • "给SL06和ST01各设置了20% off，到月底"
  • "报名了TikTok 6.6大促，报了SL06和ST01"
  • "上架了SL08，定价₱99"
  • "给SL07创建了GMV Max广告，预算₱500"
  • "把首页Banner换成了6.6主题"

🔍 **查询命令**
  • "今天做了什么" — 查看今日操作汇总
  • "SL07最近更新了吗" — 查询某个产品的操作历史
  • "最近有什么操作" — 查看最近5条记录
  • "查视频更新" — 按操作类型查询

📊 **分析命令**
  • "分析我的习惯" — 查看运营习惯分析报告
  • "周报" — 生成本周运营汇总

❓ **其他**
  • "帮助" / "?" — 显示此清单
  • "退出" / "exit" — 退出
═══════════════════════════════════════
""")


# ====================== 主程序入口 ======================
def main():
    logger = OperationsLogger()
    
    if len(sys.argv) > 1:
        args = sys.argv[1:]
        cmd = args[0]
        
        if cmd in ["--summary", "-s"]:
            print(logger.today_summary())
        elif cmd in ["--weekly", "-w"]:
            print(logger.weekly_summary())
        elif cmd in ["--analyze", "-a"]:
            print(logger.analyze_habits())
        elif cmd in ["--ask", "-q"] and len(args) > 1:
            print(logger.query(" ".join(args[1:])))
        elif cmd in ["--help", "-h"]:
            print(__doc__)
        else:
            # 当作操作记录处理
            text = " ".join(args)
            record, insights = logger.process(text)
            print(f"\n✅ **已记录！**\n")
            print(logger._format_record_short(record))
            if insights:
                print("")
                for insight in insights:
                    print(insight)
    else:
        # 交互式模式
        logger.interactive()


if __name__ == "__main__":
    main()
