"""
创意视频数据分析脚本
功能：从 SQLite 读取视频数据 -> 生成分析报告 -> 存入 Layer2_Working
用法：python analyze_creatives.py [店铺代码] [周数]

分析维度：
1. 整体概览 - 视频总数、有产出视频数、总GMV、总ROI
2. 商品维度 - 各商品关联的视频数、达人数量、视频GMV贡献
3. 达人维度 - Top 达人、ROI排名、授权类型分布
4. 视频质量 - 2秒/6秒播放率分布、高转化视频特征
5. 行动建议
"""

import sqlite3
import os
import sys
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'Layer1_Permanent', '01_My_Shop', 'shop_data.db')
REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'Layer2_Working')


def get_connection():
    if not os.path.exists(DB_PATH):
        print(f'[X] 数据库不存在: {DB_PATH}')
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_week_ranges(cursor, weeks=2):
    """获取最近 N 周的周范围"""
    cursor.execute('''
        SELECT DISTINCT week_start, week_end 
        FROM video_weekly_perf
        ORDER BY week_start DESC
        LIMIT ?
    ''', (weeks,))
    rows = cursor.fetchall()
    return list(reversed(rows))


def analyze_creatives(weeks=2):
    conn = get_connection()
    cursor = conn.cursor()

    week_ranges = get_week_ranges(cursor, weeks)
    if not week_ranges:
        print('[X] 没有视频数据')
        conn.close()
        return

    w_latest = week_ranges[-1]
    w_previous = week_ranges[0] if len(week_ranges) > 1 else None

    report_lines = []
    period_str = f"{w_latest['week_start']} ~ {w_latest['week_end']}"
    if w_previous:
        period_str = f"{w_previous['week_start']} ~ {w_latest['week_end']}"

    report_lines.append(f"# 创意视频数据分析报告（{period_str}）")
    report_lines.append("")
    report_lines.append(f"> 分析日期：{datetime.now().strftime('%Y/%m/%d')}")
    report_lines.append(f"> 数据范围：{w_latest['week_start']} ~ {w_latest['week_end']}")
    report_lines.append(f"> 货币单位：美元（USD）")
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")

    # ===== 一、整体概览 =====
    report_lines.append("## 一、整体概览")
    report_lines.append("")

    # 最新周数据
    cursor.execute('''
        SELECT 
            COUNT(DISTINCT vp.video_id) as total_videos,
            COUNT(DISTINCT CASE WHEN vp.revenue > 0 THEN vp.video_id END) as active_videos,
            COUNT(DISTINCT vc.username) as total_creators,
            SUM(vp.revenue) as total_revenue,
            SUM(vp.sku_orders) as total_orders,
            SUM(vp.cost) as total_cost,
            SUM(vp.ad_impressions) as total_impressions,
            AVG(vp.roi) as avg_roi,
            AVG(vp.play_2s_rate) as avg_2s,
            AVG(vp.play_6s_rate) as avg_6s
        FROM video_weekly_perf vp
        LEFT JOIN video_creatives vc ON vp.video_id = vc.video_id
        WHERE vp.week_start = ? AND vp.week_end = ?
    ''', (w_latest['week_start'], w_latest['week_end']))
    latest = cursor.fetchone()

    total_videos = latest['total_videos'] or 0
    active_videos = latest['active_videos'] or 0
    total_revenue = latest['total_revenue'] or 0
    total_orders = latest['total_orders'] or 0
    total_cost = latest['total_cost'] or 0
    total_impressions = latest['total_impressions'] or 0
    avg_roi = latest['avg_roi'] or 0
    avg_2s = latest['avg_2s'] or 0
    avg_6s = latest['avg_6s'] or 0

    report_lines.append("| 指标 | 本周数值 |")
    report_lines.append("| :--- | :--- |")
    report_lines.append(f"| 视频总数 | {total_videos} |")
    report_lines.append(f"| 有产出视频数 | {active_videos} |")
    report_lines.append(f"| 达人数量 | {latest['total_creators'] or 0} |")
    report_lines.append(f"| 视频总收入 (USD) | ${total_revenue:,.2f} |")
    report_lines.append(f"| 总订单数 | {total_orders} |")
    report_lines.append(f"| 总广告花费 (USD) | ${total_cost:,.2f} |")
    report_lines.append(f"| 平均 ROI | {avg_roi:.2f}x |")
    report_lines.append(f"| 总广告曝光 | {total_impressions:,} |")
    report_lines.append(f"| 平均 2 秒播放率 | {avg_2s*100:.2f}% |")
    report_lines.append(f"| 平均 6 秒播放率 | {avg_6s*100:.2f}% |")

    # 环比
    if w_previous:
        cursor.execute('''
            SELECT 
                SUM(revenue) as total_revenue,
                SUM(sku_orders) as total_orders,
                SUM(cost) as total_cost,
                AVG(roi) as avg_roi
            FROM video_weekly_perf
            WHERE week_start = ? AND week_end = ?
        ''', (w_previous['week_start'], w_previous['week_end']))
        prev = cursor.fetchone()
        prev_rev = prev['total_revenue'] or 0
        if prev_rev > 0:
            rev_change = (total_revenue - prev_rev) / prev_rev * 100
            report_lines.append(f"| 收入环比 | {rev_change:+.1f}% |")

    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")

    # ===== 二、商品视频表现 =====
    report_lines.append("## 二、商品视频表现 Top 10")
    report_lines.append("")

    cursor.execute('''
        SELECT 
            vp.platform_product_id,
            p.product_name,
            COUNT(DISTINCT vp.video_id) as video_count,
            COUNT(DISTINCT vc.username) as creator_count,
            SUM(vp.revenue) as total_revenue,
            SUM(vp.sku_orders) as total_orders,
            SUM(vp.cost) as total_cost,
            CASE WHEN SUM(vp.cost) > 0 THEN SUM(vp.revenue)/SUM(vp.cost) ELSE 0 END as roi,
            SUM(vp.ad_impressions) as total_impressions
        FROM video_weekly_perf vp
        LEFT JOIN products p ON vp.platform_product_id = p.platform_product_id
        LEFT JOIN video_creatives vc ON vp.video_id = vc.video_id
        WHERE vp.week_start = ? AND vp.week_end = ?
            AND vp.platform_product_id != '0'
        GROUP BY vp.platform_product_id
        ORDER BY total_revenue DESC
        LIMIT 10
    ''', (w_latest['week_start'], w_latest['week_end']))
    product_videos = cursor.fetchall()

    if product_videos:
        report_lines.append("| 排名 | 商品名 | 视频数 | 达人 | 收入 (USD) | 订单 | ROI | 广告曝光 |")
        report_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for i, pv in enumerate(product_videos):
            name = str(pv['product_name'] or pv['platform_product_id'])[:35]
            report_lines.append(
                f"| {i+1} | {name}... | {pv['video_count']} | {pv['creator_count']} | "
                f"${pv['total_revenue']:,.2f} | {pv['total_orders']} | "
                f"{pv['roi']:.2f}x | {pv['total_impressions']:,} |"
            )
    else:
        report_lines.append("（暂无数据）")
    report_lines.append("")

    # ===== 三、达人表现 Top 15 =====
    report_lines.append("## 三、达人表现 Top 15")
    report_lines.append("")

    cursor.execute('''
        SELECT 
            vc.username,
            COUNT(DISTINCT vp.video_id) as video_count,
            SUM(vp.revenue) as total_revenue,
            SUM(vp.sku_orders) as total_orders,
            SUM(vp.cost) as total_cost,
            CASE WHEN SUM(vp.cost) > 0 THEN SUM(vp.revenue)/SUM(vp.cost) ELSE 0 END as roi,
            SUM(vp.ad_impressions) as total_impressions,
            GROUP_CONCAT(DISTINCT vpl.authorization_type) as auth_types
        FROM video_weekly_perf vp
        JOIN video_creatives vc ON vp.video_id = vc.video_id
        LEFT JOIN video_product_link vpl ON vp.video_id = vpl.video_id AND vp.platform_product_id = vpl.platform_product_id
        WHERE vp.week_start = ? AND vp.week_end = ?
        GROUP BY vc.username
        ORDER BY total_revenue DESC
        LIMIT 15
    ''', (w_latest['week_start'], w_latest['week_end']))
    creators = cursor.fetchall()

    if creators:
        report_lines.append("| 排名 | 达人 | 视频数 | 收入 (USD) | 订单 | ROI | 广告曝光 | 授权类型 |")
        report_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for i, cr in enumerate(creators):
            auth = str(cr['auth_types'] or '—')[:20]
            report_lines.append(
                f"| {i+1} | {cr['username']} | {cr['video_count']} | "
                f"${cr['total_revenue']:,.2f} | {cr['total_orders']} | "
                f"{cr['roi']:.2f}x | {cr['total_impressions']:,} | {auth} |"
            )
    else:
        report_lines.append("（暂无数据）")
    report_lines.append("")

    # ===== 四、视频质量分析 =====
    report_lines.append("## 四、视频质量分析")
    report_lines.append("")

    # 2秒播放率分布
    cursor.execute('''
        SELECT 
            CASE 
                WHEN play_2s_rate >= 0.5 THEN '>=50%'
                WHEN play_2s_rate >= 0.3 THEN '30-50%'
                WHEN play_2s_rate >= 0.15 THEN '15-30%'
                ELSE '<15%'
            END as bucket,
            COUNT(*) as cnt,
            AVG(revenue) as avg_revenue,
            AVG(roi) as avg_roi
        FROM video_weekly_perf
        WHERE week_start = ? AND week_end = ?
        GROUP BY bucket
        ORDER BY bucket DESC
    ''', (w_latest['week_start'], w_latest['week_end']))
    play_2s_dist = cursor.fetchall()

    report_lines.append("### 2 秒播放率分布")
    report_lines.append("")
    report_lines.append("| 区间 | 视频数 | 占比 | 平均收入 | 平均 ROI |")
    report_lines.append("| :--- | :--- | :--- | :--- | :--- |")
    for row in play_2s_dist:
        pct = row['cnt'] / total_videos * 100 if total_videos > 0 else 0
        report_lines.append(
            f"| {row['bucket']} | {row['cnt']} | {pct:.1f}% | "
            f"${row['avg_revenue']:.2f} | {row['avg_roi']:.2f}x |"
        )
    report_lines.append("")

    # 6秒播放率分布
    cursor.execute('''
        SELECT 
            CASE 
                WHEN play_6s_rate >= 0.3 THEN '>=30%'
                WHEN play_6s_rate >= 0.15 THEN '15-30%'
                WHEN play_6s_rate >= 0.05 THEN '5-15%'
                ELSE '<5%'
            END as bucket,
            COUNT(*) as cnt,
            AVG(revenue) as avg_revenue,
            AVG(roi) as avg_roi
        FROM video_weekly_perf
        WHERE week_start = ? AND week_end = ?
        GROUP BY bucket
        ORDER BY bucket DESC
    ''', (w_latest['week_start'], w_latest['week_end']))
    play_6s_dist = cursor.fetchall()

    report_lines.append("### 6 秒播放率分布")
    report_lines.append("")
    report_lines.append("| 区间 | 视频数 | 占比 | 平均收入 | 平均 ROI |")
    report_lines.append("| :--- | :--- | :--- | :--- | :--- |")
    for row in play_6s_dist:
        pct = row['cnt'] / total_videos * 100 if total_videos > 0 else 0
        report_lines.append(
            f"| {row['bucket']} | {row['cnt']} | {pct:.1f}% | "
            f"${row['avg_revenue']:.2f} | {row['avg_roi']:.2f}x |"
        )
    report_lines.append("")

    # 高转化视频特征
    report_lines.append("### 高 ROI 视频特征（ROI > 3）")
    report_lines.append("")

    cursor.execute('''
        SELECT 
            COUNT(*) as high_roi_count,
            AVG(play_2s_rate) as avg_2s,
            AVG(play_6s_rate) as avg_6s,
            AVG(ad_ctr) as avg_ctr,
            AVG(ad_conversion_rate) as avg_cvr
        FROM video_weekly_perf
        WHERE week_start = ? AND week_end = ? AND roi > 3
    ''', (w_latest['week_start'], w_latest['week_end']))
    high_roi = cursor.fetchone()

    cursor.execute('''
        SELECT 
            COUNT(*) as low_roi_count,
            AVG(play_2s_rate) as avg_2s,
            AVG(play_6s_rate) as avg_6s,
            AVG(ad_ctr) as avg_ctr,
            AVG(ad_conversion_rate) as avg_cvr
        FROM video_weekly_perf
        WHERE week_start = ? AND week_end = ? AND roi <= 1 AND revenue > 0
    ''', (w_latest['week_start'], w_latest['week_end']))
    low_roi = cursor.fetchone()

    report_lines.append("| 指标 | 高 ROI 视频 (ROI>3) | 低 ROI 视频 (ROI<=1) |")
    report_lines.append("| :--- | :--- | :--- |")
    report_lines.append(f"| 视频数 | {high_roi['high_roi_count']} | {low_roi['low_roi_count']} |")
    report_lines.append(f"| 平均 2 秒播放率 | {high_roi['avg_2s']*100:.1f}% | {low_roi['avg_2s']*100:.1f}% |")
    report_lines.append(f"| 平均 6 秒播放率 | {high_roi['avg_6s']*100:.1f}% | {low_roi['avg_6s']*100:.1f}% |")
    report_lines.append(f"| 平均广告 CTR | {high_roi['avg_ctr']*100:.2f}% | {low_roi['avg_ctr']*100:.2f}% |")
    report_lines.append(f"| 平均广告 CVR | {high_roi['avg_cvr']*100:.2f}% | {low_roi['avg_cvr']*100:.2f}% |")
    report_lines.append("")

    # ===== 五、授权类型分布 =====
    report_lines.append("## 五、授权类型分布")
    report_lines.append("")

    cursor.execute('''
        SELECT 
            vpl.authorization_type,
            COUNT(DISTINCT vp.video_id) as video_count,
            COUNT(DISTINCT vc.username) as creator_count,
            SUM(vp.revenue) as total_revenue,
            SUM(vp.sku_orders) as total_orders,
            CASE WHEN SUM(vp.cost) > 0 THEN SUM(vp.revenue)/SUM(vp.cost) ELSE 0 END as roi
        FROM video_weekly_perf vp
        JOIN video_product_link vpl ON vp.video_id = vpl.video_id AND vp.platform_product_id = vpl.platform_product_id
        JOIN video_creatives vc ON vp.video_id = vc.video_id
        WHERE vp.week_start = ? AND vp.week_end = ?
        GROUP BY vpl.authorization_type
        ORDER BY total_revenue DESC
    ''', (w_latest['week_start'], w_latest['week_end']))
    auth_dist = cursor.fetchall()

    if auth_dist:
        report_lines.append("| 授权类型 | 视频数 | 达人 | 收入 (USD) | 订单 | ROI |")
        report_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for row in auth_dist:
            report_lines.append(
                f"| {row['authorization_type']} | {row['video_count']} | {row['creator_count']} | "
                f"${row['total_revenue']:,.2f} | {row['total_orders']} | {row['roi']:.2f}x |"
            )
    else:
        report_lines.append("（暂无数据）")
    report_lines.append("")

    # ===== 六、行动建议 =====
    report_lines.append("## 六、行动建议")
    report_lines.append("")

    suggestions = []

    # 1. 高 ROI 达人追加
    if creators:
        top_creator = creators[0]
        if top_creator['roi'] > 2:
            suggestions.append({
                'title': f'追加合作高 ROI 达人 {top_creator["username"]}',
                'finding': f'该达人本周贡献 ${top_creator["total_revenue"]:.2f}，ROI {top_creator["roi"]:.2f}x',
                'action': '联系追加合作，提供更多商品链接或专属优惠码',
                'effect': '预计可提升 15-30% 视频渠道 GMV'
            })

    # 2. 视频覆盖不足的商品
    cursor.execute('''
        SELECT p.product_name, p.platform_product_id,
            COALESCE(v.video_count, 0) as video_count,
            pw.video_gmv
        FROM products p
        JOIN product_weekly pw ON p.product_id = pw.product_id
        LEFT JOIN (
            SELECT platform_product_id, COUNT(DISTINCT video_id) as video_count
            FROM video_weekly_perf
            WHERE week_start = ? AND week_end = ?
            GROUP BY platform_product_id
        ) v ON p.platform_product_id = v.platform_product_id
        WHERE pw.week_start = ? AND pw.week_end = ?
            AND p.status = 'Active'
            AND pw.video_gmv > 0
        ORDER BY pw.video_gmv DESC
        LIMIT 5
    ''', (w_latest['week_start'], w_latest['week_end'],
          w_latest['week_start'], w_latest['week_end']))
    low_video_products = cursor.fetchall()

    for pv in low_video_products:
        if pv['video_count'] < 3 and pv['video_gmv'] > 50:
            suggestions.append({
                'title': f'增加 {str(pv["product_name"])[:25]} 的视频覆盖',
                'finding': f'该商品视频 GMV ${pv["video_gmv"]:.2f}，但仅 {pv["video_count"]} 个视频',
                'action': '追加 5-10 条达人视频，设置更高联盟佣金吸引达人',
                'effect': f'视频数从 {pv["video_count"]} 提升至 10+，GMV 预计增长 50%+'
            })

    # 3. 视频质量优化
    if avg_2s < 0.2:
        suggestions.append({
            'title': '优化视频前 2 秒吸引力',
            'finding': f'平均 2 秒播放率仅 {avg_2s*100:.1f}%，低于行业基准',
            'action': '视频开头使用强钩子（价格对比/效果展示/悬念），前 3 秒必须抓住注意力',
            'effect': '2 秒播放率提升至 25%+，预计广告 ROI 提升 20%'
        })

    # 4. 授权类型优化
    if auth_dist:
        best_auth = max(auth_dist, key=lambda x: x['roi'])
        worst_auth = min(auth_dist, key=lambda x: x['roi'])
        if best_auth['roi'] > worst_auth['roi'] * 1.5:
            suggestions.append({
                'title': f'优先发展 {best_auth["authorization_type"]} 类型达人',
                'finding': f'{best_auth["authorization_type"]} ROI {best_auth["roi"]:.2f}x vs {worst_auth["authorization_type"]} {worst_auth["roi"]:.2f}x',
                'action': '调整达人招募策略，优先与高 ROI 授权类型的达人合作',
                'effect': '整体视频 ROI 预计提升 15%'
            })

    # 5. 零产出视频清理
    zero_videos = total_videos - active_videos
    if zero_videos > total_videos * 0.5:
        suggestions.append({
            'title': '评估零产出视频，优化投放策略',
            'finding': f'{zero_videos}/{total_videos} 视频无产出（{zero_videos/total_videos*100:.0f}%）',
            'action': '对持续 2 周无产出的视频暂停广告投放，将预算集中到高 ROI 视频',
            'effect': '广告花费效率提升 20-30%'
        })

    for i, s in enumerate(suggestions):
        report_lines.append(f"### [行动项 {i+1}]：{s['title']}")
        report_lines.append(f"- **基于数据发现**：{s['finding']}")
        report_lines.append(f"- **建议具体动作**：{s['action']}")
        report_lines.append(f"- **预期效果**：{s['effect']}")
        report_lines.append("")

    # ===== 七、总结 =====
    report_lines.append("## 七、总结")
    report_lines.append("")
    report_lines.append("```")
    report_lines.append(f"视频健康度：{'[OK] 优秀' if active_videos/total_videos > 0.3 else '[WARN] 待提升'}（{active_videos}/{total_videos} 视频有产出）")
    report_lines.append(f"ROI 表现：   {'[OK] 优秀' if avg_roi > 2 else '[WARN] 待优化'}（平均 ROI {avg_roi:.2f}x）")
    report_lines.append(f"视频质量：   {'[OK] 良好' if avg_2s > 0.25 else '[WARN] 需优化'}（2 秒播放率 {avg_2s*100:.1f}%）")
    report_lines.append(f"达人矩阵：   {len(creators)} 位达人有产出")
    report_lines.append("```")
    report_lines.append("")

    # 优先级
    report_lines.append("**优先级排序：**")
    report_lines.append("")
    for i, s in enumerate(suggestions):
        report_lines.append(f"{i+1}. {s['title']}")

    report_lines.append("")

    # ===== 写入文件 =====
    os.makedirs(REPORT_DIR, exist_ok=True)
    date_str = w_latest['week_start'].replace('-', '')
    if w_previous:
        date_str = w_previous['week_start'].replace('-', '') + '-' + w_latest['week_end'].replace('-', '')

    filename = f"创意视频分析_{date_str}.md"
    filepath = os.path.join(REPORT_DIR, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))

    print(f'[OK] 报告已生成: {filepath}')
    print(f'     视频: {total_videos} 个, 有产出: {active_videos} 个')
    print(f'     收入: ${total_revenue:,.2f}, ROI: {avg_roi:.2f}x')
    print(f'     建议: {len(suggestions)} 条')

    conn.close()
    return filepath


if __name__ == '__main__':
    weeks = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    analyze_creatives(weeks)
