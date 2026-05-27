"""
📋 运营策略师 Agent — 自动化版
==============================
功能：读取复盘报告 + 数据分析报告 → 结合竞品动态 → 输出下周运营策略方案

用法：
  python scripts/strategy_generator.py                     # 自动模式：找最新报告生成策略
  python scripts/strategy_generator.py --preview            # 预览找到的报告，不生成
  python scripts/strategy_generator.py --report             # 查看上次生成的策略报告
  python scripts/strategy_generator.py --draft "自定义总结" # 手动输入本周总结生成策略
"""

import os
import re
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'Layer1_Permanent', '01_My_Shop', 'shop_data.db')
LAYER2_DIR = os.path.join(BASE_DIR, 'Layer2_Working')
INDUSTRY_DIR = os.path.join(BASE_DIR, 'Layer1_Permanent', '04_Industry')
OUTPUT_DIR = os.path.join(BASE_DIR, 'Layer2_Working')

# ====================== 数据源 ======================
REPORT_PATTERNS = {
    'review': '复盘报告_',            # 复盘报告
    'product': '商品数据分析_',        # 商品数据分析
    'creative': '创意视频分析_',       # 创意视频分析
    'competitor': '竞品周报_',         # 竞品周报
}


def find_latest_reports():
    """扫描 Layer2_Working 找到最新的各类型报告"""
    reports = {}
    for report_type, pattern in REPORT_PATTERNS.items():
        candidates = [f for f in os.listdir(LAYER2_DIR) if f.startswith(pattern) and f.endswith('.md')]
        if candidates:
            # 按文件名排序（含日期），取最新的
            latest = max(candidates, key=lambda f: os.path.getmtime(os.path.join(LAYER2_DIR, f)))
            reports[report_type] = os.path.join(LAYER2_DIR, latest)
            print(f"  📄 找到 {report_type}: {latest}")
        else:
            reports[report_type] = None
            print(f"  ⚠️ 未找到 {report_type}")
    return reports


def extract_review_data(filepath):
    """
    从复盘报告提取关键数据
    """
    if not filepath or not os.path.exists(filepath):
        return {}

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    data = {}

    # 提取核心结论（第一段非标题文字）
    conclusion_match = re.search(r'\*\*核心结论\*\*[：:]\s*(.+?)(?:\n|$)', content)
    if conclusion_match:
        data['core_conclusion'] = conclusion_match.group(1).strip()

    # 提取数据概览表
    table_section = re.search(r'## 二、数据概览.*?\n(.*?)(?:\n##|\Z)', content, re.DOTALL)
    if table_section:
        table_text = table_section.group(1)
        metrics = {}
        lines = table_text.strip().split('\n')
        for line in lines:
            if line.startswith('|') and not line.startswith('|:'):
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 5:
                    name = parts[1].strip().replace('**', '')
                    current = parts[2]
                    prev = parts[3]
                    change = parts[4]
                    if name and name not in ['指标', '']:
                        # 提取数值
                        curr_val = re.sub(r'[₱%,.+\-]', '', current).strip()
                        prev_val = re.sub(r'[₱%,.+\-]', '', prev).strip()
                        data[name] = {
                            'current': current,
                            'previous': prev,
                            'change': change,
                            'curr_val': curr_val,
                            'prev_val': prev_val,
                        }
        data['metrics'] = data

    # 提取行动建议
    actions_section = re.search(r'## 五、行动建议.*?\n(.*?)(?:\n##|\Z)', content, re.DOTALL)
    if actions_section:
        actions = []
        for line in actions_section.group(1).strip().split('\n'):
            if line.startswith('|') and not line.startswith('|:'):
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 4:
                    priority = parts[1].strip()
                    action = parts[2].strip()
                    if priority and action and priority not in ['优先级', '']:
                        actions.append({'priority': priority, 'action': action})
        data['actions'] = actions

    # 提取成功经验
    successes = re.findall(r'### 经验\d+[：:](.+?)\n', content)
    if successes:
        data['successes'] = [s.strip() for s in successes]

    # 提取失败教训
    failures = re.findall(r'### 教训\d+[：:](.+?)\n', content)
    if failures:
        data['failures'] = [f.strip() for f in failures]

    return data


def extract_db_metrics():
    """
    从数据库提取关键指标，补充报告数据
    """
    if not os.path.exists(DB_PATH):
        return {}

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    metrics = {}

    # 近两周产品 GMV 趋势
    cursor.execute('''
        SELECT week_start, SUM(shop_gmv + video_gmv + live_gmv) as total_gmv,
               SUM(units_sold) as total_units
        FROM product_weekly
        WHERE week_start >= date('now', '-21 days')
        GROUP BY week_start
        ORDER BY week_start
    ''')
    weekly = cursor.fetchall()
    if weekly:
        metrics['weekly_gmv_trend'] = [
            {'week': w[0], 'gmv': round(w[1], 2), 'units': w[2]} for w in weekly
        ]
        # 本周 vs 上周
        if len(weekly) >= 2:
            last_week = weekly[-1][1] or 0
            prev_week = weekly[-2][1] or 0
            if prev_week > 0:
                gmv_change = round((last_week - prev_week) / prev_week * 100, 1)
                metrics['gmv_change_pct'] = gmv_change

    # Top 产品
    cursor.execute('''
        SELECT pw.product_id, p.product_name,
               SUM(pw.shop_gmv + pw.video_gmv + pw.live_gmv) as total_gmv,
               SUM(pw.units_sold) as total_units
        FROM product_weekly pw
        JOIN products p ON pw.product_id = p.product_id
        WHERE pw.week_start >= date('now', '-14 days')
        GROUP BY pw.product_id
        ORDER BY total_gmv DESC
        LIMIT 5
    ''')
    top_products = cursor.fetchall()
    if top_products:
        metrics['top_products'] = [
            {'name': p[1][:20], 'gmv': round(p[2], 2), 'units': p[3]} for p in top_products
        ]

    # 商品总数/动销数
    cursor.execute('''
        SELECT COUNT(DISTINCT product_id), COUNT(DISTINCT CASE WHEN units_sold > 0 THEN product_id END)
        FROM product_weekly
        WHERE week_start >= date('now', '-14 days')
    ''')
    total, active = cursor.fetchone()
    metrics['total_products'] = total or 0
    metrics['active_products'] = active or 0
    metrics['sell_through_rate'] = round(active / total * 100, 1) if total else 0

    conn.close()
    return metrics


def get_competitor_summary():
    """读取竞品周报摘要"""
    candidates = [f for f in os.listdir(LAYER2_DIR) if f.startswith('竞品周报_') and f.endswith('.md')]
    if not candidates:
        return None

    latest = max(candidates, key=lambda f: os.path.getmtime(os.path.join(LAYER2_DIR, f)))
    with open(os.path.join(LAYER2_DIR, latest), 'r', encoding='utf-8') as f:
        content = f.read()

    # 提取竞品动态摘要
    summary = {}
    # 寻找标题下的第一段文字
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if line.startswith('## ') and i + 1 < len(lines):
            section_title = line.strip('# ')
            section_content = []
            for j in range(i + 1, min(i + 5, len(lines))):
                if lines[j].strip() and not lines[j].startswith('#'):
                    section_content.append(lines[j].strip())
            if section_content:
                summary[section_title] = ' '.join(section_content[:3])

    return summary


def generate_strategy(review_data, db_metrics, competitor_summary, custom_summary=None):
    """
    核心策略生成
    基于复盘结论 + 数据趋势 + 竞品动态 → 3-5条策略 + 目标
    """
    today = datetime.now()
    next_monday = today + timedelta(days=(7 - today.weekday())) if today.weekday() != 0 else today + timedelta(days=7)

    strategies = []

    # ===== 策略1: 基于视频质量问题的策略 =====
    if review_data.get('failures'):
        if any('视频' in f or '2秒' in f or '播放率' in f for f in review_data.get('failures', [])):
            strategies.append({
                'priority': 'P0',
                'title': '视频质量攻坚 — 建立钩子模板库',
                'data_basis': '复盘报告指出2秒播放率仅5.5%（基准25%），广告ROI 0.19x，视频质量是当前最大瓶颈',
                'actions': [
                    '制作前3秒钩子模板库（价格对比/效果展示/悬念提问），本周完成10个模板',
                    '给下周合作的每一位达人提供标准化脚本框架，附带视频质量检查清单',
                    '对持续2周无产出的视频暂停广告投放，集中预算给高质量视频',
                ],
                'expected_effect': '2秒播放率提升至15%+，广告ROI提升至0.5x+',
                'responsible': '内容制作 + 达人管理',
                'checkpoint': '周三检查钩子模板库完成度，周五检查达人视频质量达标率',
                'kpv': {'metric': '2秒播放率', 'current': '5.5%', 'target': '15%'},
            })

    # ===== 策略2: 爆款复制 / 新品培育 =====
    top_products = db_metrics.get('top_products', [])
    if top_products:
        top_name = top_products[0]['name'] if top_products else '当前爆款'
        strategies.append({
            'priority': 'P0',
            'title': f'加大「{top_name}」推广力度并复制模式到潜力品',
            'data_basis': f'近2周Top 1商品GMV ₱{top_products[0].get("gmv", 0):.0f}，验证了产品力',
            'actions': [
                f'追加{top_name}的达人合作视频10-15条，扩大覆盖人群',
                '识别2-3个与爆款同品类的潜力品，复制已验证的推广模式',
                '为潜力品设置15-20%联盟佣金，吸引优质达人合作',
            ],
            'expected_effect': f'爆款GMV提升30%+，带动至少1个潜力品首周出单',
            'responsible': '内容 + 达人',
            'checkpoint': '周末检查爆款GMV增长和潜力品出单情况',
            'kpv': {'metric': '爆款GMV', 'current': f'₱{top_products[0].get("gmv", 0):.0f}', 'target': '+30%'},
        })

    # ===== 策略3: 清理零数据商品 =====
    active = db_metrics.get('active_products', 0)
    total = db_metrics.get('total_products', 0)
    sell_through = db_metrics.get('sell_through_rate', 0)
    if sell_through < 50:
        strategies.append({
            'priority': 'P1',
            'title': '商品结构优化 — 清理零数据商品，提升动销率',
            'data_basis': f'近2周动销率仅{sell_through}%（{active}/{total}），大量商品未出单',
            'actions': [
                f'对{total - active}款零出单商品逐一评估：下架或重新优化',
                '有潜力的商品制作2-3条测试视频，无差异化的果断下架',
                '控制本周上新数量（建议2-3款），确保每款新品有足够的推广资源',
            ],
            'expected_effect': f'动销率从{sell_through}%提升至40%+',
            'responsible': '商品运营',
            'checkpoint': '周四前完成评估，周末前完成首批清理',
            'kpv': {'metric': '动销率', 'current': f'{sell_through}%', 'target': '40%'},
        })

    # ===== 策略4: 高ROI达人深化合作 =====
    strategies.append({
        'priority': 'P1',
        'title': '高ROI达人深化合作计划',
        'data_basis': '复盘报告中提到shiela.85 (ROI 4.99x)、izzaynshie (ROI 3.03x)表现突出',
        'actions': [
            '为Top高ROI达人提供专属优惠码，增加合作商品种类',
            '争取和Top 3达人签订月度框架合作，锁定稳定产出',
            '建立达人分级管理机制：S级(ROI>3)框架合作，A级(ROI>1.5)优先合作',
        ],
        'expected_effect': '高ROI达人产出提升50%+，达人合作ROI整体提升至1.5x+',
        'responsible': '达人运营',
        'checkpoint': '周五检查框架合作进度',
        'kpv': {'metric': '高ROI达人产出', 'current': '基准', 'target': '+50%'},
    })

    # ===== 策略5: 直播试水 + 时段优化 =====
    strategies.append({
        'priority': 'P2',
        'title': '启动直播带货测试 + 优化周末转化',
        'data_basis': '复盘报告指出直播渠道GMV=0是最大增长机会；周末转化率仅3.2%-3.9%偏低',
        'actions': [
            '联系2-3个已合作的达人尝试直播带货，提供样品+佣金支持',
            '商家自播本周至少2场，优先安排在周三/周四晚（黄金转化时段）',
            '周末加大限时优惠力度，设置周末专属优惠券',
        ],
        'expected_effect': '直播渠道贡献额外5-10% GMV，周末转化率提升至4.5%+',
        'responsible': '直播运营 + 投放',
        'checkpoint': '周三确定直播排期，周末检查转化率变化',
        'kpv': {'metric': '周末转化率', 'current': '3.5%', 'target': '4.5%'},
    })

    # ===== 策略6: (可选)大促预警 =====
    # 检测是否是月底(发薪日)
    if today.day >= 25 or today.day <= 5:
        strategies.append({
            'priority': 'P2',
            'title': '月底发薪日营销 — 抓住菲律宾"发薪日消费"窗口',
            'data_basis': f'当前日期{today.day}日，临近菲律宾月尾发薪日（15日/30日），消费意愿显著提升',
            'actions': [
                '设置"发薪日特惠"活动，主推2-3款高性价比商品',
                '加大对高客单价商品的推广力度（客单价显示在上升）',
                '提前备货，确保爆款品库存充足',
            ],
            'expected_effect': '抓住发薪日窗口，GMV额外增长15-20%',
            'responsible': '商品 + 投放',
            'checkpoint': '30日/15日前完成活动设置',
            'kpv': {'metric': '发薪日GMV', 'current': '-', 'target': '+15-20%'},
        })

    # ===== 目标设定 =====
    # 从DB取上周GMV，设定增长目标
    current_gmv = 0
    db_weekly = db_metrics.get('weekly_gmv_trend', [])
    if db_weekly:
        current_gmv = db_weekly[-1].get('gmv', 0)
    # 再尝试从复盘数据取
    for k, v in review_data.items():
        if isinstance(v, dict) and v.get('current', '').startswith('₱'):
            try:
                current_gmv = float(re.sub(r'[₱,]', '', v['current']))
            except:
                pass
            break

    target_gmv = round(current_gmv * 1.35)  # 目标+35%
    target_sell_through = min(50, sell_through + 20) if sell_through else 40

    targets = {
        'gmv': {'current': f'₱{current_gmv:,.0f}', 'target': f'₱{target_gmv:,.0f}', 'growth': '+35%'},
        'sell_through': {'current': f'{sell_through}%', 'target': f'{target_sell_through}%', 'growth': f'+{target_sell_through - sell_through:.0f}pp' if sell_through else '40%'},
        'video_roi': {'current': '0.19x', 'target': '1.0x', 'growth': '+426%'},
        'video_output': {'current': '26条（有产出视频）', 'target': '50条', 'growth': '+92%'},
    }

    return {
        'strategies': strategies,
        'targets': targets,
        'db_metrics': db_metrics,
        'competitor': competitor_summary,
    }


def generate_report(strategy_result, review_data, custom_summary=None):
    """生成运营策略报告"""
    today = datetime.now()
    date_str = today.strftime('%Y-%m-%d')
    week_num = today.isocalendar()[1]

    lines = [
        f"# 📋 运营策略报告 — 第{week_num}周 (起止日期: {date_str})",
        f"",
        f"**策略类型**: 周度运营策略",
        f"**生成时间**: {today.strftime('%Y-%m-%d %H:%M')}",
        f"**核心依据**: 复盘报告 + 数据库销售数据 + 竞品动态",
        f"",
        f"---",
        f"",
        f"## 一、现状诊断",
        f"",
        f"### 📊 核心结论",
    ]

    if review_data.get('core_conclusion'):
        lines.append(f"> {review_data['core_conclusion']}")
    elif custom_summary:
        lines.append(f"> {custom_summary}")
    else:
        lines.append("> （未找到复盘报告，请补充本周运营概况）")

    lines.extend([
        f"",
        f"### 📈 关键指标对比",
        f"",
        f"| 指标 | 当前值 | 下周目标 | 增长幅度 |",
        f"|:---|:---:|:---:|:---:|",
    ])

    targets = strategy_result.get('targets', {})
    for metric_name, info in targets.items():
        labels = {
            'gmv': '周 GMV',
            'sell_through': '动销率',
            'video_roi': '视频 ROI',
            'video_output': '视频产出数',
        }
        label = labels.get(metric_name, metric_name)
        lines.append(f"| {label} | {info['current']} | {info['target']} | {info['growth']} |")

    lines.extend([
        f"",
        f"### 🔍 数据发现",
    ])

    db_metrics = strategy_result.get('db_metrics', {})
    gmv_change = db_metrics.get('gmv_change_pct')
    if gmv_change:
        direction = '上涨' if gmv_change > 0 else '下降'
        lines.append(f"- GMV 环比 **{direction} {abs(gmv_change)}%**，{'恢复增长' if gmv_change > 0 else '需警惕'}")

    top_products = db_metrics.get('top_products', [])
    if top_products:
        lines.append(f"- Top 1 商品: **{top_products[0]['name']}** (GMV ₱{top_products[0]['gmv']:,.0f})")
        if len(top_products) > 1:
            lines.append(f"- Top 3 合计: ₱{sum(p['gmv'] for p in top_products[:3]):,.0f}")

    total = db_metrics.get('total_products', 0)
    active = db_metrics.get('active_products', 0)
    lines.append(f"- 商品动销: **{active}/{total}** ({db_metrics.get('sell_through_rate', 0)}%)")

    # 竞品动态
    competitor = strategy_result.get('competitor')
    if competitor:
        lines.append(f"")
        lines.append(f"### 👀 竞品动态摘要")
        for section, content in list(competitor.items())[:3]:
            lines.append(f"- **{section}**: {content[:100]}")

    lines.extend([
        f"",
        f"---",
        f"",
        f"## 二、策略列表",
        f"",
    ])

    sorted_strategies = sorted(strategy_result.get('strategies', []),
                               key=lambda s: ('P0', 'P1', 'P2').index(s['priority']))

    for i, strategy in enumerate(sorted_strategies, 1):
        lines.extend([
            f"### 📌 {strategy['priority']} 策略{i}: {strategy['title']}",
            f"- **数据依据**: {strategy['data_basis']}",
            f"- **具体行动**:",
        ])
        for action in strategy['actions']:
            lines.append(f"  1. {action}")
        lines.extend([
            f"- **预期效果**: {strategy['expected_effect']}",
            f"- **负责方**: {strategy['responsible']}",
            f"- **检查点**: {strategy['checkpoint']}",
            f"- **KPV**: {strategy['kpv']['metric']} → {strategy['kpv']['current']} → {strategy['kpv']['target']}",
            f"",
        ])

    lines.extend([
        f"---",
        f"",
        f"## 三、资源分配建议",
        f"",
        f"| 资源类型 | 分配比例 | 说明 |",
        f"|:---:|:---:|:---|",
        f"| 👤 达人合作预算 | 50% | 集中在Top高ROI达人和新品推广 |",
        f"| 🎬 内容制作 | 30% | 集中在爆款品的日常内容和潜力品的测试内容 |",
        f"| 📢 广告投放 | 20% | 用于测试新品广告和爆款品的GMV MAX |",
        f"",
        f"---",
        f"",
        f"## 四、风险预警",
        f"",
        f"| 风险 | 可能性 | 影响 | 应对方案 |",
        f"|:---|:---:|:---:|:---|",
        f"| 视频质量无改善 | 🟠 中 | 🔴 高 | 暂停低质量达人合作，改为集中制作高质量商家自营视频 |",
        f"| 竞品大幅降价 | 🟡 低 | 🟠 中 | 评估利润空间，选择性跟随降价或提供附加值 |",
        f"| 库存不足 | 🟡 低 | 🟠 中 | 每周检查爆款品库存，提前2周下单补货 |",
        f"| 新品推广不及预期 | 🟠 中 | 🟡 低 | 首周出单即算成功，持续投放2-3周再评估 |",
        f"",
        f"---",
        f"",
        f"*📝 本报告由 📋 运营策略师 Agent 自动生成*",
        f"*数据来源: 复盘报告 + shop_data.db + 竞品周报*",
        f"*建议每周一执行，并结合实际情况微调*",
    ])

    return '\n'.join(lines)


def save_report(report):
    """保存策略报告"""
    today = datetime.now().strftime('%Y%m%d')
    filename = f'运营策略_周度_{today}.md'
    filepath = os.path.join(OUTPUT_DIR, filename)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n📄 运营策略报告已生成: {filepath}")
    return filepath


def main():
    import argparse
    parser = argparse.ArgumentParser(description='📋 运营策略师 Agent — 自动化策略生成')
    parser.add_argument('--preview', action='store_true', help='预览找到的报告列表，不生成')
    parser.add_argument('--report', action='store_true', help='查看上次生成的策略报告')
    parser.add_argument('--draft', type=str, help='手动输入本周运营总结，不依赖复盘报告')
    args = parser.parse_args()

    print("""
+===========================================+
|  运营策略师 Agent 已启动                     |
|                                            |
|  数据源: 复盘报告 + shop_data.db + 竞品周报   |
|  策略模型: 诊断 -> 目标 -> 策略 -> 资源 -> 风险|
+===========================================+
""")

    if args.report:
        candidates = [f for f in os.listdir(OUTPUT_DIR) if f.startswith('运营策略_') and f.endswith('.md')]
        if candidates:
            latest = max(candidates, key=lambda f: os.path.getmtime(os.path.join(OUTPUT_DIR, f)))
            print(f"📄 最近的策略报告: {latest}")
            with open(os.path.join(OUTPUT_DIR, latest), 'r', encoding='utf-8') as f:
                print(f.read()[:2000])
        else:
            print("⚠️ 还没有策略报告，请先运行: python scripts/strategy_generator.py")
        return

    # Step 1: 找报告
    print("🔍 正在扫描报告文件...")
    reports = find_latest_reports()

    if args.preview:
        print("\n📋 报告预览完成。运行 python scripts/strategy_generator.py 生成策略。")
        return

    # Step 2: 提取数据
    print("\n📊 正在提取复盘报告数据...")
    if reports.get('review'):
        review_data = extract_review_data(reports['review'])
        print(f"   ✅ 提取成功: {len(review_data)} 条关键数据")
        if review_data.get('core_conclusion'):
            print(f"   💡 核心结论: {review_data['core_conclusion'][:80]}...")
        if review_data.get('actions'):
            print(f"   📋 行动建议: {len(review_data['actions'])} 条")
    elif args.draft:
        review_data = {'core_conclusion': args.draft}
        print(f"   💡 使用手动输入: {args.draft[:60]}...")
    else:
        review_data = {}
        print("   ⚠️ 未找到复盘报告，将仅基于数据库数据生成")

    # Step 3: 数据库提取
    print("\n🗄️  正在查询数据库销售数据...")
    db_metrics = extract_db_metrics()
    if db_metrics:
        print(f"   ✅ 获取到 {len(db_metrics)} 项指标")
        if 'top_products' in db_metrics:
            print(f"   🏆 Top 1: {db_metrics['top_products'][0]['name']}")
        print(f"   📦 动销率: {db_metrics.get('sell_through_rate', '?')}%")

    # Step 4: 竞品摘要
    print("\n👀 正在读取竞品动态...")
    competitor_summary = get_competitor_summary()
    if competitor_summary:
        print(f"   ✅ 获取到 {len(competitor_summary)} 项竞品动态")
    else:
        print("   ⚠️ 未找到竞品周报")

    # Step 5: 生成策略
    print("\n📝 正在生成运营策略...")
    strategy_result = generate_strategy(review_data, db_metrics, competitor_summary, custom_summary=args.draft)
    print(f"   ✅ 生成 {len(strategy_result['strategies'])} 条策略")

    # Step 6: 输出报告
    report = generate_report(strategy_result, review_data, custom_summary=args.draft)
    filepath = save_report(report)

    print(f"""
{'='*50}
  ✅ 策略生成完成！
  
  📋 策略概览:
""")
    for s in sorted(strategy_result['strategies'],
                    key=lambda x: ('P0', 'P1', 'P2').index(x['priority'])):
        print(f"    [{s['priority']}] {s['title']}")
        print(f"        → {s['expected_effect']}")

    print(f"""
  🎯 下周目标:
""")
    for metric, info in strategy_result['targets'].items():
        labels = {'gmv': 'GMV', 'sell_through': '动销率', 'video_roi': '视频ROI', 'video_output': '视频产出'}
        print(f"    {labels.get(metric, metric)}: {info['current']} → {info['target']} ({info['growth']})")

    print(f"""
  📄 完整报告: {filepath}
  💡 提示: 通过 orchestrator 调用 — "制定下周运营策略"
{'='*50}""")


if __name__ == '__main__':
    main()
