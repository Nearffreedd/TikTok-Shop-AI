"""
GMV MAX 广告投放数据分析模块
功能：从 SQLite 读取 GMV MAX 数据 -> 生成分析文本块 -> 供周报集成
用法：python analyze_gmvmax.py [周数]

输出：返回 Markdown 格式的分析文本，可直接嵌入周度运营复盘报告
"""

import sqlite3
import os
import sys
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'Layer1_Permanent', '01_My_Shop', 'shop_data.db')


def get_connection():
    if not os.path.exists(DB_PATH):
        print(f'[X] 数据库不存在: {DB_PATH}')
        return None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_week_ranges(cursor, weeks=2):
    """获取最近 N 周的周范围"""
    cursor.execute('''
        SELECT DISTINCT week_start, week_end 
        FROM gmvmax_campaign_weekly
        ORDER BY week_start DESC
        LIMIT ?
    ''', (weeks,))
    rows = cursor.fetchall()
    return list(reversed(rows))


def analyze_gmvmax(weeks=2):
    """生成 GMV MAX 广告分析 Markdown 文本"""
    conn = get_connection()
    if not conn:
        return ""

    cursor = conn.cursor()

    week_ranges = get_week_ranges(cursor, weeks)
    if not week_ranges:
        conn.close()
        return "> ⏳ 暂无 GMV MAX 广告投放数据"

    w_latest = week_ranges[-1]
    w_previous = week_ranges[0] if len(week_ranges) > 1 else None

    lines = []
    lines.append("## 三、GMV MAX 广告投放分析")
    lines.append("")
    lines.append(f"> 数据周期：{w_latest['week_start']} ~ {w_latest['week_end']} | 货币单位：USD")
    lines.append("")

    # ===== 3.1 广告投放概览 =====
    lines.append("### 3.1 广告投放概览")
    lines.append("")

    cursor.execute('''
        SELECT 
            COUNT(*) as total_campaigns,
            COUNT(CASE WHEN cost > 0 THEN 1 END) as active_campaigns,
            SUM(cost) as total_cost,
            SUM(net_cost) as total_net_cost,
            SUM(sku_orders) as total_orders,
            SUM(total_revenue) as total_revenue,
            CASE WHEN SUM(cost) > 0 THEN SUM(total_revenue)/SUM(cost) ELSE 0 END as overall_roi
        FROM gmvmax_campaign_weekly
        WHERE week_start = ? AND week_end = ?
    ''', (w_latest['week_start'], w_latest['week_end']))
    latest = cursor.fetchone()

    total_cost = latest['total_cost'] or 0
    total_revenue = latest['total_revenue'] or 0
    total_orders = latest['total_orders'] or 0
    overall_roi = latest['overall_roi'] or 0
    active_campaigns = latest['active_campaigns'] or 0

    lines.append("| 指标 | 本周数值 |")
    lines.append("| :--- | :--- |")
    lines.append(f"| 广告计划总数 | {latest['total_campaigns']} |")
    lines.append(f"| 有花费计划数 | {active_campaigns} |")
    lines.append(f"| 总花费 (USD) | ${total_cost:,.2f} |")
    lines.append(f"| 总收入 (USD) | ${total_revenue:,.2f} |")
    lines.append(f"| 总订单数 | {total_orders} |")
    lines.append(f"| 综合 ROI | {overall_roi:.2f}x |")

    # 环比
    if w_previous:
        cursor.execute('''
            SELECT 
                SUM(cost) as total_cost,
                SUM(total_revenue) as total_revenue,
                SUM(sku_orders) as total_orders,
                CASE WHEN SUM(cost) > 0 THEN SUM(total_revenue)/SUM(cost) ELSE 0 END as overall_roi
            FROM gmvmax_campaign_weekly
            WHERE week_start = ? AND week_end = ?
        ''', (w_previous['week_start'], w_previous['week_end']))
        prev = cursor.fetchone()
        prev_cost = prev['total_cost'] or 0
        prev_rev = prev['total_revenue'] or 0
        prev_roi = prev['overall_roi'] or 0

        if prev_cost > 0:
            cost_change = (total_cost - prev_cost) / prev_cost * 100
            lines.append(f"| 花费环比 | {cost_change:+.1f}% |")
        if prev_rev > 0:
            rev_change = (total_revenue - prev_rev) / prev_rev * 100
            lines.append(f"| 收入环比 | {rev_change:+.1f}% |")
        lines.append(f"| 上周综合 ROI | {prev_roi:.2f}x |")

    lines.append("")

    # ===== 3.2 各广告计划表现排名 =====
    lines.append("### 3.2 各广告计划表现排名（按收入）")
    lines.append("")

    cursor.execute('''
        SELECT 
            campaign_name,
            product_code,
            product_code2,
            target_roi,
            cost,
            net_cost,
            sku_orders,
            total_revenue,
            roi,
            current_budget
        FROM gmvmax_campaign_weekly
        WHERE week_start = ? AND week_end = ? AND cost > 0
        ORDER BY total_revenue DESC
    ''', (w_latest['week_start'], w_latest['week_end']))
    active_plans = cursor.fetchall()

    if active_plans:
        lines.append("| 排名 | 广告计划 | 产品 | 目标ROI | 花费 | 收入 | 实际ROI | 订单 | 预算 |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for i, p in enumerate(active_plans):
            product_str = p['product_code'] or '—'
            if p['product_code2']:
                product_str += f"&{p['product_code2']}"
            target = f"{p['target_roi']:.1f}x" if p['target_roi'] else '—'
            name_short = str(p['campaign_name'])[:30]
            lines.append(
                f"| {i+1} | {name_short}... | {product_str} | {target} | "
                f"${p['cost']:.2f} | ${p['total_revenue']:.2f} | "
                f"{p['roi']:.2f}x | {p['sku_orders']} | ${p['current_budget']:.0f} |"
            )
    else:
        lines.append("（本周无活跃广告计划）")
    lines.append("")

    # ===== 3.3 产品维度广告汇总 =====
    lines.append("### 3.3 产品维度广告汇总")
    lines.append("")

    cursor.execute('''
        SELECT 
            COALESCE(product_code, 'OTHER') as prod_code,
            COUNT(*) as campaign_count,
            SUM(cost) as total_cost,
            SUM(total_revenue) as total_revenue,
            SUM(sku_orders) as total_orders,
            CASE WHEN SUM(cost) > 0 THEN SUM(total_revenue)/SUM(cost) ELSE 0 END as roi,
            AVG(target_roi) as avg_target_roi
        FROM gmvmax_campaign_weekly
        WHERE week_start = ? AND week_end = ? AND cost > 0
        GROUP BY prod_code
        ORDER BY total_cost DESC
    ''', (w_latest['week_start'], w_latest['week_end']))
    product_summary = cursor.fetchall()

    if product_summary:
        lines.append("| 产品 | 计划数 | 总花费 | 总收入 | 订单 | 广告ROI | 平均目标ROI |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for ps in product_summary:
            # 尝试获取产品名称
            cursor.execute('''
                SELECT style_name FROM style_catalog WHERE style_code = ?
            ''', (ps['prod_code'],))
            style_row = cursor.fetchone()
            prod_name = style_row['style_name'] if style_row else ps['prod_code']

            avg_target = f"{ps['avg_target_roi']:.1f}x" if ps['avg_target_roi'] else '—'
            lines.append(
                f"| {prod_name} ({ps['prod_code']}) | {ps['campaign_count']} | "
                f"${ps['total_cost']:.2f} | ${ps['total_revenue']:.2f} | "
                f"{ps['total_orders']} | {ps['roi']:.2f}x | {avg_target} |"
            )
    else:
        lines.append("（本周无活跃广告计划）")
    lines.append("")

    # ===== 3.4 广告 ROI vs 目标 ROI 达成率 =====
    lines.append("### 3.4 广告 ROI 达成分析")
    lines.append("")

    cursor.execute('''
        SELECT 
            campaign_name,
            product_code,
            target_roi,
            roi,
            cost,
            total_revenue,
            CASE WHEN target_roi > 0 THEN roi / target_roi ELSE NULL END as achievement_rate
        FROM gmvmax_campaign_weekly
        WHERE week_start = ? AND week_end = ? AND cost > 0 AND target_roi IS NOT NULL
        ORDER BY achievement_rate DESC
    ''', (w_latest['week_start'], w_latest['week_end']))
    roi_achievement = cursor.fetchall()

    if roi_achievement:
        lines.append("| 广告计划 | 产品 | 目标ROI | 实际ROI | 达成率 | 评级 |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for ra in roi_achievement:
            rate = ra['achievement_rate'] if ra['achievement_rate'] else 0
            if rate >= 1.0:
                rating = '[达标]'
            elif rate >= 0.7:
                rating = '[接近]'
            else:
                rating = '[未达标]'
            name_short = str(ra['campaign_name'])[:25]
            lines.append(
                f"| {name_short}... | {ra['product_code'] or '—'} | "
                f"{ra['target_roi']:.1f}x | {ra['roi']:.2f}x | "
                f"{rate*100:.0f}% | {rating} |"
            )
    else:
        lines.append("（无带目标 ROI 的活跃广告计划）")
    lines.append("")

    # ===== 3.5 行动建议 =====
    lines.append("### 3.5 广告投放行动建议")
    lines.append("")

    suggestions = []

    # 1. 高 ROI 计划追加预算
    cursor.execute('''
        SELECT campaign_name, product_code, roi, cost, current_budget
        FROM gmvmax_campaign_weekly
        WHERE week_start = ? AND week_end = ? AND roi > 3 AND cost > 0
        ORDER BY roi DESC
        LIMIT 3
    ''', (w_latest['week_start'], w_latest['week_end']))
    high_roi_plans = cursor.fetchall()

    for hp in high_roi_plans:
        suggestions.append({
            'title': f'追加 {hp["campaign_name"][:20]} 预算',
            'finding': f'ROI {hp["roi"]:.2f}x，花费 ${hp["cost"]:.2f}，当前预算 ${hp["current_budget"]:.0f}',
            'action': f'将预算从 ${hp["current_budget"]:.0f} 提升至 ${hp["current_budget"]*2:.0f}，扩大高 ROI 投放规模',
            'effect': f'预计可增加 ${hp["cost"]*hp["roi"]*0.5:.0f} 额外收入'
        })

    # 2. 低 ROI 计划优化或暂停
    cursor.execute('''
        SELECT campaign_name, product_code, roi, cost, total_revenue
        FROM gmvmax_campaign_weekly
        WHERE week_start = ? AND week_end = ? AND roi < 1 AND cost > 5
        ORDER BY roi ASC
        LIMIT 3
    ''', (w_latest['week_start'], w_latest['week_end']))
    low_roi_plans = cursor.fetchall()

    for lp in low_roi_plans:
        suggestions.append({
            'title': f'优化/暂停 {lp["campaign_name"][:20]}',
            'finding': f'ROI 仅 {lp["roi"]:.2f}x，花费 ${lp["cost"]:.2f}，收入 ${lp["total_revenue"]:.2f}',
            'action': '检查视频素材质量、目标人群定向、出价策略，若连续 2 周 ROI<1 则暂停',
            'effect': '节省低效花费，预计可提升整体 ROI 0.3-0.5x'
        })

    # 3. 产品广告覆盖建议
    cursor.execute('''
        SELECT 
            COALESCE(product_code, 'OTHER') as prod_code,
            SUM(cost) as total_cost,
            SUM(total_revenue) as total_revenue,
            CASE WHEN SUM(cost) > 0 THEN SUM(total_revenue)/SUM(cost) ELSE 0 END as roi
        FROM gmvmax_campaign_weekly
        WHERE week_start = ? AND week_end = ? AND cost > 0
        GROUP BY prod_code
        ORDER BY total_cost DESC
    ''', (w_latest['week_start'], w_latest['week_end']))
    prod_ad = cursor.fetchall()

    # 找出有商品 GMV 但无广告投入的产品
    cursor.execute('''
        SELECT p.product_name, p.platform_product_id, pw.gmv, pw.video_gmv
        FROM products p
        JOIN product_weekly pw ON p.product_id = pw.product_id
        WHERE pw.week_start = ? AND pw.week_end = ?
            AND pw.gmv > 0
            AND p.platform_product_id NOT IN (
                SELECT DISTINCT '0' FROM gmvmax_campaign_weekly
                WHERE week_start = ? AND week_end = ? AND cost > 0
            )
        ORDER BY pw.gmv DESC
        LIMIT 3
    ''', (w_latest['week_start'], w_latest['week_end'],
          w_latest['week_start'], w_latest['week_end']))
    no_ad_products = cursor.fetchall()

    for nap in no_ad_products:
        suggestions.append({
            'title': f'为 {str(nap["product_name"])[:20]} 创建 GMV MAX 广告',
            'finding': f'该商品 GMV ${nap["gmv"]:.2f}（视频 ${nap["video_gmv"]:.2f}），但无 GMV MAX 广告覆盖',
            'action': '创建 1-2 个 GMV MAX 广告计划，设置目标 ROI 2.5-3.0，预算 $20-50',
            'effect': '预计可提升该商品 20-40% GMV'
        })

    # 4. 整体 ROI 评估
    if overall_roi < 1.5:
        suggestions.append({
            'title': '整体广告 ROI 待提升',
            'finding': f'综合 ROI {overall_roi:.2f}x，低于健康线 2.0x',
            'action': '审查所有广告计划的视频素材质量，暂停 ROI<1 的计划，将预算集中到 ROI>2 的计划',
            'effect': '目标将整体 ROI 提升至 2.0x+'
        })
    elif overall_roi > 3:
        suggestions.append({
            'title': '广告 ROI 表现优秀，可考虑扩量',
            'finding': f'综合 ROI {overall_roi:.2f}x，表现优秀',
            'action': '逐步增加预算（每次 20-30%），测试是否可维持 ROI 水平',
            'effect': '在保持 ROI 的前提下最大化 GMV'
        })

    for i, s in enumerate(suggestions):
        lines.append(f"**{i+1}. {s['title']}**")
        lines.append(f"- [数据] **数据发现**：{s['finding']}")
        lines.append(f"- [动作] **建议动作**：{s['action']}")
        lines.append(f"- [效果] **预期效果**：{s['effect']}")
        lines.append("")

    conn.close()
    return '\n'.join(lines)


def get_ad_summary_for_weekly_report(weeks=2):
    """获取广告数据摘要，供周报核心指标表使用
    返回: dict { total_cost, total_revenue, roi, orders, active_campaigns }
    """
    conn = get_connection()
    if not conn:
        return {}

    cursor = conn.cursor()
    week_ranges = get_week_ranges(cursor, weeks)
    if not week_ranges:
        conn.close()
        return {}

    result = {}
    for wr in week_ranges:
        cursor.execute('''
            SELECT 
                SUM(cost) as total_cost,
                SUM(total_revenue) as total_revenue,
                SUM(sku_orders) as total_orders,
                COUNT(CASE WHEN cost > 0 THEN 1 END) as active_campaigns,
                CASE WHEN SUM(cost) > 0 THEN SUM(total_revenue)/SUM(cost) ELSE 0 END as roi
            FROM gmvmax_campaign_weekly
            WHERE week_start = ? AND week_end = ?
        ''', (wr['week_start'], wr['week_end']))
        row = cursor.fetchone()
        key = f"{wr['week_start']}_{wr['week_end']}"
        result[key] = {
            'total_cost': row['total_cost'] or 0,
            'total_revenue': row['total_revenue'] or 0,
            'total_orders': row['total_orders'] or 0,
            'active_campaigns': row['active_campaigns'] or 0,
            'roi': row['roi'] or 0,
        }

    conn.close()
    return result


if __name__ == '__main__':
    weeks = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    result = analyze_gmvmax(weeks)
    print(result)
