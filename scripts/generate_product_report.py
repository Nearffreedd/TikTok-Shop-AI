"""
商品数据分析报告生成脚本
功能：从 SQLite 数据库读取数据 → 按 SOP 生成分析报告 → 存入 Layer2_Working
用法：python generate_product_report.py [店铺代码] [周数]

示例：
  python generate_product_report.py PNB 2    # 分析 PNB 最近 2 周
  python generate_product_report.py PNB       # 默认最近 2 周
  python generate_product_report.py           # 默认 PNB 最近 2 周
"""

import sqlite3
import os
import sys
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                       'Layer1_Permanent', '01_My_Shop', 'shop_data.db')
REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                          'Layer2_Working')

def get_connection():
    if not os.path.exists(DB_PATH):
        print(f'❌ 数据库不存在: {DB_PATH}')
        print('   请先运行: python scripts/init_database.py')
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_shop_id(cursor, shop_code):
    cursor.execute('SELECT shop_id, shop_name FROM shops WHERE shop_code = ?', (shop_code,))
    row = cursor.fetchone()
    if row is None:
        print(f'❌ 店铺 {shop_code} 不存在')
        sys.exit(1)
    return row['shop_id'], row['shop_name']

def get_weekly_data(cursor, shop_id, weeks=2):
    """获取最近 N 周的周数据"""
    cursor.execute('''
        SELECT DISTINCT week_start, week_end 
        FROM product_weekly pw
        JOIN products p ON pw.product_id = p.product_id
        WHERE p.shop_id = ?
        ORDER BY week_start DESC
        LIMIT ?
    ''', (shop_id, weeks))
    
    week_ranges = cursor.fetchall()
    if len(week_ranges) == 0:
        print('❌ 没有找到周数据')
        sys.exit(1)
    
    # 按时间正序排列
    week_ranges = list(reversed(week_ranges))
    
    all_data = []
    for wr in week_ranges:
        cursor.execute('''
            SELECT 
                p.platform_product_id,
                p.product_name,
                p.status,
                p.style_id,
                sc.style_code,
                sc.style_name,
                pw.*
            FROM product_weekly pw
            JOIN products p ON pw.product_id = p.product_id
            LEFT JOIN style_catalog sc ON p.style_id = sc.style_id
            WHERE p.shop_id = ? AND pw.week_start = ? AND pw.week_end = ?
            ORDER BY pw.gmv DESC
        ''', (shop_id, wr['week_start'], wr['week_end']))
        week_data = cursor.fetchall()
        all_data.append({
            'week_start': wr['week_start'],
            'week_end': wr['week_end'],
            'products': week_data
        })
    
    return all_data

def get_style_data(cursor, shop_id):
    """获取款式关联信息"""
    cursor.execute('''
        SELECT p.platform_product_id, sc.style_code, sc.style_name
        FROM products p
        LEFT JOIN style_catalog sc ON p.style_id = sc.style_id
        WHERE p.shop_id = ?
    ''', (shop_id,))
    return {row['platform_product_id']: row for row in cursor.fetchall()}

def generate_report(shop_code='PNB', weeks=2):
    conn = get_connection()
    cursor = conn.cursor()
    
    shop_id, shop_name = get_shop_id(cursor, shop_code)
    all_data = get_weekly_data(cursor, shop_id, weeks)
    style_map = get_style_data(cursor, shop_id)
    
    # 准备数据
    w_latest = all_data[-1]  # 最新一周
    w_previous = all_data[0] if len(all_data) > 1 else None
    
    latest_products = w_latest['products']
    total_gmv = sum(p['gmv'] for p in latest_products)
    total_units = sum(p['units_sold'] for p in latest_products)
    active_with_sales = [p for p in latest_products if p['status'] == 'Active' and p['gmv'] > 0]
    zero_data = [p for p in latest_products if p['status'] == 'Active' and p['gmv'] == 0]
    total_active = len([p for p in latest_products if p['status'] == 'Active'])
    
    # 构建周环比数据
    wow_data = {}
    if w_previous:
        prev_by_id = {p['platform_product_id']: p for p in w_previous['products'] if p['gmv'] > 0}
        curr_by_id = {p['platform_product_id']: p for p in latest_products if p['gmv'] > 0}
        
        # 共同商品
        for pid in set(prev_by_id.keys()) & set(curr_by_id.keys()):
            pp = prev_by_id[pid]
            cp = curr_by_id[pid]
            gmv_change = ((cp['gmv'] - pp['gmv']) / pp['gmv'] * 100) if pp['gmv'] > 0 else 0
            wow_data[pid] = {
                'prev_gmv': pp['gmv'],
                'curr_gmv': cp['gmv'],
                'change_pct': gmv_change,
                'prev_video_imp': pp['video_impressions'],
                'curr_video_imp': cp['video_impressions'],
            }
        
        # 新品
        new_products = [curr_by_id[pid] for pid in set(curr_by_id.keys()) - set(prev_by_id.keys())]
    else:
        new_products = []
    
    # ===== 开始生成报告 =====
    report_lines = []
    
    # 标题
    period_str = f"{w_latest['week_start']} ~ {w_latest['week_end']}"
    if w_previous:
        period_str = f"{w_previous['week_start']} ~ {w_latest['week_end']}"
    
    report_lines.append(f"# 商品数据分析报告 — {shop_name}（{period_str}）")
    report_lines.append("")
    report_lines.append(f"> 分析日期：{datetime.now().strftime('%Y/%m/%d')}")
    report_lines.append(f"> 店铺：{shop_name}（{shop_code}）")
    report_lines.append(f"> 数据范围：{w_latest['week_start']} ~ {w_latest['week_end']}")
    report_lines.append(f"> 分析方法：商品数据分析 SOP v1.0")
    report_lines.append(f"> 货币单位：菲律宾比索（₱）")
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")
    
    # ===== 一、商品总览 =====
    report_lines.append("## 一、商品总览")
    report_lines.append("")
    report_lines.append("| 指标 | 数值 |")
    report_lines.append("| :--- | :--- |")
    report_lines.append(f"| 在售商品总数 | {total_active} |")
    report_lines.append(f"| 有出单商品数 | {len(active_with_sales)} |")
    report_lines.append(f"| 零数据商品数 | {len(zero_data)} |")
    report_lines.append(f"| **总 GMV** | **₱{total_gmv:,.2f}** |")
    report_lines.append(f"| **总成交件数** | **{total_units}** |")
    
    if w_previous:
        prev_total_gmv = sum(p['gmv'] for p in w_previous['products'] if p['status'] == 'Active')
        prev_total_units = sum(p['units_sold'] for p in w_previous['products'] if p['status'] == 'Active')
        gmv_change = ((total_gmv - prev_total_gmv) / prev_total_gmv * 100) if prev_total_gmv > 0 else 0
        unit_change = ((total_units - prev_total_units) / prev_total_units * 100) if prev_total_units > 0 else 0
        report_lines.append(f"| GMV 环比 | **{gmv_change:+.1f}%** |")
        report_lines.append(f"| 件数环比 | **{unit_change:+.1f}%** |")
    
    report_lines.append("")
    
    # ===== 二、商品贡献度排名 =====
    report_lines.append("## 二、商品贡献度排名")
    report_lines.append("")
    report_lines.append(f"### {w_latest['week_start']} ~ {w_latest['week_end']} 商品排名")
    report_lines.append("")
    report_lines.append("| 排名 | 商品名 | GMV | 占比 | 成交件数 | 款式 | 核心渠道 | 层级 |")
    report_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    
    sorted_products = sorted(active_with_sales, key=lambda x: x['gmv'], reverse=True)
    for i, p in enumerate(sorted_products):
        name = str(p['product_name'])[:40]
        gmv = p['gmv']
        pct = gmv / total_gmv * 100 if total_gmv > 0 else 0
        units = int(p['units_sold'])
        
        # 款式
        style_info = ''
        if p['style_code']:
            style_info = f"{p['style_code']} ({p['style_name']})"
        
        # 核心渠道
        channels = {
            '视频': p['video_gmv'],
            '商城': p['shop_gmv'],
            '商品卡': p['card_gmv'],
            '直播': p['live_gmv']
        }
        main_ch = max(channels, key=channels.get)
        main_pct = max(channels.values()) / gmv * 100 if gmv > 0 else 0
        
        # 层级
        if i < 2 or gmv > 5000:
            level = '🔥 爆款'
        elif i < 5 or gmv > 1000:
            level = '⭐ 潜力款'
        elif gmv > 0:
            level = '📌 长尾款'
        else:
            level = '⚪ 零数据'
        
        report_lines.append(f"| {i+1} | {name}... | ₱{gmv:,.2f} | {pct:.1f}% | {units} | {style_info} | {main_ch}({main_pct:.0f}%) | {level} |")
    
    # 零数据商品汇总
    if zero_data:
        report_lines.append(f"| {len(sorted_products)+1}-{total_active} | 其余 {len(zero_data)} 款商品 | ₱0 | 0% | 0 | — | — | ⚪ 零数据 |")
    
    report_lines.append("")
    
    # 集中度
    report_lines.append("### 集中度分析")
    report_lines.append("")
    report_lines.append("| 指标 | 数值 |")
    report_lines.append("| :--- | :--- |")
    if len(sorted_products) >= 1:
        report_lines.append(f"| **Top 1 商品占比** | {sorted_products[0]['gmv']/total_gmv*100:.1f}% |")
    if len(sorted_products) >= 2:
        top2_pct = sum(p['gmv'] for p in sorted_products[:2]) / total_gmv * 100
        report_lines.append(f"| **Top 2 商品占比** | {top2_pct:.1f}% |")
    if len(sorted_products) >= 3:
        top3_pct = sum(p['gmv'] for p in sorted_products[:3]) / total_gmv * 100
        report_lines.append(f"| **Top 3 商品占比** | {top3_pct:.1f}% |")
    report_lines.append("")
    
    # ===== 三、渠道归因分析 =====
    report_lines.append("## 三、渠道归因分析")
    report_lines.append("")
    
    video_total = sum(p['video_gmv'] for p in latest_products)
    shop_total = sum(p['shop_gmv'] for p in latest_products)
    card_total = sum(p['card_gmv'] for p in latest_products)
    live_total = sum(p['live_gmv'] for p in latest_products)
    
    report_lines.append("| 渠道 | GMV | 占比 |")
    report_lines.append("| :--- | :--- | :--- |")
    report_lines.append(f"| 🎬 **视频渠道** | ₱{video_total:,.2f} | **{video_total/total_gmv*100:.1f}%** |" if total_gmv > 0 else "| 🎬 视频渠道 | ₱0 | 0% |")
    report_lines.append(f"| 🏪 **商城渠道** | ₱{shop_total:,.2f} | {shop_total/total_gmv*100:.1f}% |" if total_gmv > 0 else "| 🏪 商城渠道 | ₱0 | 0% |")
    report_lines.append(f"| 📦 **商品卡渠道** | ₱{card_total:,.2f} | {card_total/total_gmv*100:.1f}% |" if total_gmv > 0 else "| 📦 商品卡渠道 | ₱0 | 0% |")
    report_lines.append(f"| 📡 **直播渠道** | ₱{live_total:,.2f} | {live_total/total_gmv*100:.1f}% |" if total_gmv > 0 else "| 📡 直播渠道 | ₱0 | 0% |")
    report_lines.append("")
    
    # 各商品渠道明细
    if active_with_sales:
        report_lines.append("### 各商品渠道分布明细")
        report_lines.append("")
        report_lines.append("| 商品 | 款式 | 视频 GMV | 视频占比 | 商城 GMV | 商城占比 | 商品卡 GMV | 商品卡占比 |")
        report_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for p in sorted_products:
            name = str(p['product_name'])[:30]
            style_tag = p['style_code'] if p['style_code'] else '—'
            v_pct = p['video_gmv'] / p['gmv'] * 100 if p['gmv'] > 0 else 0
            s_pct = p['shop_gmv'] / p['gmv'] * 100 if p['gmv'] > 0 else 0
            c_pct = p['card_gmv'] / p['gmv'] * 100 if p['gmv'] > 0 else 0
            report_lines.append(f"| {name}... | {style_tag} | ₱{p['video_gmv']:,.2f} | {v_pct:.1f}% | ₱{p['shop_gmv']:,.2f} | {s_pct:.1f}% | ₱{p['card_gmv']:,.2f} | {c_pct:.1f}% |")
        report_lines.append("")
    
    # ===== 四、视频创意深度下钻 =====
    report_lines.append("## 四、视频创意深度下钻")
    report_lines.append("")
    
    # 查询该店铺下各商品的视频表现
    cursor.execute('''
        SELECT 
            vp.platform_product_id,
            COUNT(DISTINCT vp.video_id) as video_count,
            COUNT(DISTINCT vc.username) as creator_count,
            SUM(vp.revenue) as total_revenue,
            SUM(vp.sku_orders) as total_orders,
            SUM(vp.cost) as total_cost,
            CASE WHEN SUM(vp.cost) > 0 THEN SUM(vp.revenue)/SUM(vp.cost) ELSE 0 END as roi,
            SUM(vp.ad_impressions) as total_impressions
        FROM video_weekly_perf vp
        JOIN products p ON vp.platform_product_id = p.platform_product_id
        LEFT JOIN video_creatives vc ON vp.video_id = vc.video_id
        WHERE p.shop_id = ? AND vp.week_start = ? AND vp.week_end = ?
            AND vp.platform_product_id != '0'
        GROUP BY vp.platform_product_id
        ORDER BY total_revenue DESC
    ''', (shop_id, w_latest['week_start'], w_latest['week_end']))
    video_product_data = cursor.fetchall()
    
    if video_product_data:
        report_lines.append("### 各商品视频渠道表现")
        report_lines.append("")
        report_lines.append("| 商品名 | 视频数 | 达人 | 视频收入 (USD) | 订单 | ROI | 广告曝光 |")
        report_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for vp in video_product_data:
            p = next((p for p in latest_products if p['platform_product_id'] == vp['platform_product_id']), None)
            name = str(p['product_name'])[:30] if p else str(vp['platform_product_id'])[:15]
            report_lines.append(
                f"| {name}... | {vp['video_count']} | {vp['creator_count']} | "
                f"${vp['total_revenue']:,.2f} | {vp['total_orders']} | "
                f"{vp['roi']:.2f}x | {vp['total_impressions']:,} |"
            )
        report_lines.append("")
        
        # Top 3 视频创意
        report_lines.append("### Top 5 视频创意")
        report_lines.append("")
        cursor.execute('''
            SELECT 
                vp.video_id,
                vc.video_title,
                vc.username,
                vp.revenue,
                vp.sku_orders,
                vp.roi,
                vp.play_2s_rate,
                vp.play_6s_rate,
                vp.platform_product_id
            FROM video_weekly_perf vp
            JOIN video_creatives vc ON vp.video_id = vc.video_id
            WHERE vp.week_start = ? AND vp.week_end = ?
            ORDER BY vp.revenue DESC
            LIMIT 5
        ''', (w_latest['week_start'], w_latest['week_end']))
        top_videos = cursor.fetchall()
        
        if top_videos:
            report_lines.append("| 排名 | 达人 | 视频标题 | 收入 (USD) | 订单 | ROI | 2秒播放率 | 6秒播放率 |")
            report_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
            for i, tv in enumerate(top_videos):
                title = str(tv['video_title'] or '—')[:30]
                report_lines.append(
                    f"| {i+1} | {tv['username']} | {title}... | "
                    f"${tv['revenue']:.2f} | {tv['sku_orders']} | "
                    f"{tv['roi']:.2f}x | {tv['play_2s_rate']*100:.1f}% | {tv['play_6s_rate']*100:.1f}% |"
                )
            report_lines.append("")
        
        # Top 3 达人
        report_lines.append("### Top 5 达人")
        report_lines.append("")
        cursor.execute('''
            SELECT 
                vc.username,
                COUNT(DISTINCT vp.video_id) as video_count,
                SUM(vp.revenue) as total_revenue,
                SUM(vp.sku_orders) as total_orders,
                CASE WHEN SUM(vp.cost) > 0 THEN SUM(vp.revenue)/SUM(vp.cost) ELSE 0 END as roi
            FROM video_weekly_perf vp
            JOIN video_creatives vc ON vp.video_id = vc.video_id
            WHERE vp.week_start = ? AND vp.week_end = ?
            GROUP BY vc.username
            ORDER BY total_revenue DESC
            LIMIT 5
        ''', (w_latest['week_start'], w_latest['week_end']))
        top_creators = cursor.fetchall()
        
        if top_creators:
            report_lines.append("| 排名 | 达人 | 视频数 | 收入 (USD) | 订单 | ROI |")
            report_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
            for i, tc in enumerate(top_creators):
                report_lines.append(
                    f"| {i+1} | {tc['username']} | {tc['video_count']} | "
                    f"${tc['total_revenue']:,.2f} | {tc['total_orders']} | {tc['roi']:.2f}x |"
                )
            report_lines.append("")
    else:
        report_lines.append("（本周暂无视频创意数据）")
        report_lines.append("")
    
    report_lines.append("---")
    report_lines.append("")
    
    # ===== 五、流量效率分析 =====
    report_lines.append("## 五、流量效率分析")
    report_lines.append("")
    if active_with_sales:
        report_lines.append("| 商品 | 款式 | 视频曝光 | 视频点击率 | 视频转化率 | 商城点击率 | 商城转化率 | 商品卡点击率 | 商品卡转化率 |")
        report_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for p in sorted_products:
            name = str(p['product_name'])[:25]
            style_tag = p['style_code'] if p['style_code'] else '—'
            report_lines.append(f"| {name}... | {style_tag} | {p['video_impressions']:,.0f} | {p['video_click_rate']*100:.2f}% | {p['video_conversion_rate']*100:.2f}% | {p['shop_click_rate']*100:.2f}% | {p['shop_conversion_rate']*100:.2f}% | {p['card_click_rate']*100:.2f}% | {p['card_conversion_rate']*100:.2f}% |")
        report_lines.append("")
    
    # ===== 六、周环比对比 =====
    if w_previous and wow_data:
        report_lines.append("## 六、周环比对比")
        report_lines.append("")
        report_lines.append(f"| 商品名 | 款式 | {w_previous['week_start']} GMV | {w_latest['week_start']} GMV | 环比变化 | 趋势 | 视频曝光变化 |")
        report_lines.append("| :--- | :--- | :--- | :--- | :--- | :---: | :--- |")
        
        for pid, data in sorted(wow_data.items(), key=lambda x: abs(x[1]['change_pct']), reverse=True):
            p = next((p for p in latest_products if p['platform_product_id'] == pid), None)
            if p:
                name = str(p['product_name'])[:30]
                style_tag = p['style_code'] if p['style_code'] else '—'
                trend = '📈' if data['change_pct'] > 10 else ('📉' if data['change_pct'] < -10 else '—')
                imp_change = ((data['curr_video_imp'] - data['prev_video_imp']) / data['prev_video_imp'] * 100) if data['prev_video_imp'] > 0 else 0
                report_lines.append(f"| {name}... | {style_tag} | ₱{data['prev_gmv']:,.2f} | ₱{data['curr_gmv']:,.2f} | **{data['change_pct']:+.1f}%** | {trend} | {data['prev_video_imp']:,.0f} → {data['curr_video_imp']:,.0f} ({imp_change:+.1f}%) |")
        
        report_lines.append("")
        
        # 新品
        if new_products:
            report_lines.append("### 本周新品")
            report_lines.append("")
            for p in new_products:
                name = str(p['product_name'])[:40]
                style_tag = p['style_code'] if p['style_code'] else '未关联'
                report_lines.append(f"- **{name}...** | 款式: {style_tag} | GMV: ₱{p['gmv']:,.2f} | 件数: {int(p['units_sold'])} | 核心渠道: 视频({p['video_gmv']/p['gmv']*100:.0f}%)")
            report_lines.append("")
    
    # ===== 七、异常商品清单 =====
    report_lines.append("## 七、异常商品清单")
    report_lines.append("")
    
    # 正向异常
    positive_anomalies = []
    if w_previous and wow_data:
        for pid, data in wow_data.items():
            if data['change_pct'] > 100:
                p = next((p for p in latest_products if p['platform_product_id'] == pid), None)
                if p:
                    positive_anomalies.append((str(p['product_name'])[:40], data['change_pct']))
    
    if positive_anomalies:
        report_lines.append("### 🟢 正向异常（GMV 增长 > 100%）")
        report_lines.append("")
        for name, pct in positive_anomalies:
            report_lines.append(f"- **{name}...**：GMV 环比 **+{pct:.1f}%**")
        report_lines.append("")
    
    # 负向异常
    negative_anomalies = []
    if w_previous and wow_data:
        for pid, data in wow_data.items():
            if data['change_pct'] < -50:
                p = next((p for p in latest_products if p['platform_product_id'] == pid), None)
                if p:
                    negative_anomalies.append((str(p['product_name'])[:40], data['change_pct']))
    
    if negative_anomalies:
        report_lines.append("### 🔴 负向异常（GMV 下降 > 50%）")
        report_lines.append("")
        for name, pct in negative_anomalies:
            report_lines.append(f"- **{name}...**：GMV 环比 **{pct:.1f}%**")
        report_lines.append("")
    
    # 零数据商品
    if zero_data:
        report_lines.append(f"### ⚪ 零数据商品（{len(zero_data)} 款）")
        report_lines.append("")
        report_lines.append("| 序号 | 商品名 | 款式 |")
        report_lines.append("| :--- | :--- | :--- |")
        for i, p in enumerate(zero_data):
            name = str(p['product_name'])[:45]
            style_tag = p['style_code'] if p['style_code'] else '未关联'
            report_lines.append(f"| {i+1} | {name}... | {style_tag} |")
        report_lines.append("")
    
    # ===== 八、联盟推广数据分析 =====
    report_lines.append("## 八、联盟推广数据分析")
    report_lines.append("")
    
    # 查询联盟数据（使用 week_start 匹配，因为联盟周和商品周可能差1天）
    cursor.execute('''
        SELECT 
            aw.*,
            p.platform_product_id,
            p.product_name,
            p.style_id
        FROM affiliate_weekly aw
        JOIN products p ON aw.product_id = p.product_id
        WHERE p.shop_id = ? AND aw.week_start = ?
        ORDER BY aw.affiliate_gmv DESC
    ''', (shop_id, w_latest['week_start']))
    affiliate_data = cursor.fetchall()
    
    if affiliate_data:
        # 汇总统计
        total_aff_gmv = sum(r['affiliate_gmv'] for r in affiliate_data)
        total_aff_units = sum(r['affiliate_units'] for r in affiliate_data)
        total_aff_commission = sum(r['estimated_commission'] for r in affiliate_data)
        total_creators = sum(r['selling_creators'] for r in affiliate_data)
        total_lives = sum(r['live_count'] for r in affiliate_data)
        total_videos = sum(r['video_count'] for r in affiliate_data)
        total_refunded_gmv = sum(r['refunded_gmv'] for r in affiliate_data)
        
        report_lines.append("### 联盟推广概览")
        report_lines.append("")
        report_lines.append(f"| 指标 | 数值 |")
        report_lines.append(f"| :--- | :--- |")
        report_lines.append(f"| 联盟 GMV | ₱{total_aff_gmv:,.2f} |")
        report_lines.append(f"| 联盟成交件数 | {total_aff_units} |")
        report_lines.append(f"| 预计佣金支出 | ₱{total_aff_commission:,.2f} |")
        report_lines.append(f"| 佣金占比 | {total_aff_commission/total_aff_gmv*100:.1f}% |" if total_aff_gmv > 0 else "| 佣金占比 | — |")
        report_lines.append(f"| 销售达人 | {total_creators} |")
        report_lines.append(f"| 直播场次 | {total_lives} |")
        report_lines.append(f"| 联盟视频数 | {total_videos} |")
        report_lines.append(f"| 退款 GMV | ₱{total_refunded_gmv:,.2f} |")
        report_lines.append(f"| 退款率 | {total_refunded_gmv/total_aff_gmv*100:.1f}% |" if total_aff_gmv > 0 else "| 退款率 | — |")
        report_lines.append("")
        
        # 各商品联盟表现
        report_lines.append("### 各商品联盟表现")
        report_lines.append("")
        report_lines.append("| 商品名 | 联盟 GMV | 成交件数 | 佣金 | 达人 | 直播 | 视频 | 退款 GMV |")
        report_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for ad in affiliate_data:
            name = str(ad['product_name'])[:25]
            report_lines.append(
                f"| {name}... | ₱{ad['affiliate_gmv']:,.2f} | {ad['affiliate_units']} | "
                f"₱{ad['estimated_commission']:,.2f} | {ad['selling_creators']} | "
                f"{ad['live_count']} | {ad['video_count']} | ₱{ad['refunded_gmv']:,.2f} |"
            )
        report_lines.append("")
        
        # 周环比对比（如果有前一周数据）
        if w_previous:
            cursor.execute('''
                SELECT 
                    SUM(affiliate_gmv) as prev_gmv,
                    SUM(affiliate_units) as prev_units,
                    SUM(estimated_commission) as prev_commission,
                    SUM(selling_creators) as prev_creators,
                    SUM(live_count) as prev_lives,
                    SUM(video_count) as prev_videos
                FROM affiliate_weekly aw
                JOIN products p ON aw.product_id = p.product_id
                WHERE p.shop_id = ? AND aw.week_start = ?
            ''', (shop_id, w_previous['week_start']))
            prev_aff = cursor.fetchone()
            
            if prev_aff and prev_aff['prev_gmv'] and prev_aff['prev_gmv'] > 0:
                prev_gmv = prev_aff['prev_gmv']
                gmv_change = (total_aff_gmv - prev_gmv) / prev_gmv * 100
                prev_units = prev_aff['prev_units'] or 0
                units_change = (total_aff_units - prev_units) / prev_units * 100 if prev_units > 0 else 0
                prev_creators = prev_aff['prev_creators'] or 0
                creators_change = (total_creators - prev_creators) / prev_creators * 100 if prev_creators > 0 else 0
                
                report_lines.append("### 联盟数据周环比")
                report_lines.append("")
                report_lines.append(f"| 指标 | 上期 ({w_previous['week_start']}) | 本期 ({w_latest['week_start']}) | 环比 |")
                report_lines.append(f"| :--- | :--- | :--- | :--- |")
                report_lines.append(f"| 联盟 GMV | ₱{prev_gmv:,.2f} | ₱{total_aff_gmv:,.2f} | **{gmv_change:+.1f}%** |")
                report_lines.append(f"| 成交件数 | {prev_units} | {total_aff_units} | **{units_change:+.1f}%** |")
                report_lines.append(f"| 销售达人 | {prev_creators} | {total_creators} | **{creators_change:+.1f}%** |")
                report_lines.append("")
    else:
        report_lines.append("（本周暂无联盟推广数据）")
        report_lines.append("")
    
    report_lines.append("---")
    report_lines.append("")
    
    # ===== 九、GMV MAX 广告投放分析 =====
    # 导入 analyze_gmvmax 模块并获取广告分析文本
    try:
        from analyze_gmvmax import analyze_gmvmax, get_ad_summary_for_weekly_report
        ad_analysis = analyze_gmvmax(weeks)
        if ad_analysis and not ad_analysis.startswith('> ⏳'):
            report_lines.append(ad_analysis)
            report_lines.append("---")
            report_lines.append("")
    except ImportError:
        pass
    except Exception as e:
        report_lines.append(f"> ⚠️ GMV MAX 广告数据加载异常: {e}")
        report_lines.append("")
    
    # ===== 十、行动建议 =====
    report_lines.append("## 十、行动建议")
    report_lines.append("")
    
    # 根据数据动态生成建议
    suggestions = []
    
    # 1. 爆款维护
    if sorted_products:
        top_product = sorted_products[0]
        top_name = str(top_product['product_name'])[:30]
        top_pct = top_product['gmv'] / total_gmv * 100 if total_gmv > 0 else 0
        if top_pct > 50:
            suggestions.append({
                'title': f'降低对 {top_name} 的单品依赖',
                'finding': f'Top 1 商品占 GMV 的 {top_pct:.1f}%，依赖度过高',
                'action': '加大第二梯队商品（Bible Bracelet/Citrine Bracelet）的投放，每周至少上架 2 款新品测试',
                'effect': f'Top 1 占比降至 50% 以下'
            })
    
    # 2. 新品培育
    if new_products:
        for p in new_products:
            name = str(p['product_name'])[:30]
            suggestions.append({
                'title': f'重点培育新品 {name}',
                'finding': f'新品首周 GMV ₱{p["gmv"]:,.2f}，纯视频驱动',
                'action': '追加 5-10 条视频内容，开通商城和商品卡渠道，设置联盟佣金',
                'effect': '第二周 GMV 目标翻倍'
            })
    
    # 3. 零数据清理
    if len(zero_data) > 5:
        suggestions.append({
            'title': '清理零数据商品，提升动销率',
            'finding': f'{len(zero_data)} 款商品零出单，占在售商品 {len(zero_data)/total_active*100:.0f}%',
            'action': '逐一评估：有潜力的制作 2-3 条视频测试，无差异化的果断下架',
            'effect': f'动销率从 {(len(active_with_sales)/total_active*100):.0f}% 提升至 40%+'
        })
    
    # 4. 转化优化
    low_cvr_products = [p for p in sorted_products if p['video_conversion_rate'] < 0.01 and p['video_impressions'] > 10000]
    for p in low_cvr_products:
        name = str(p['product_name'])[:30]
        suggestions.append({
            'title': f'优化 {name} 视频转化率',
            'finding': f'视频曝光 {p["video_impressions"]:,.0f} 但转化率仅 {p["video_conversion_rate"]*100:.2f}%',
            'action': '优化视频 CTA、商品详情页、增加限时优惠信息',
            'effect': f'转化率提升至 1.5%+'
        })
    
    # 5. 直播机会
    if live_total == 0:
        suggestions.append({
            'title': '启动直播带货测试',
            'finding': '直播渠道 GMV 为 0，是最大增长机会点',
            'action': '联系 2-3 个达人尝试直播，商家自播每周至少 2 场',
            'effect': '直播渠道预计贡献额外 15-20% GMV'
        })
    
    for i, s in enumerate(suggestions):
        report_lines.append(f"### [行动项 {i+1}]：{s['title']}")
        report_lines.append(f"- **基于数据发现**：{s['finding']}")
        report_lines.append(f"- **建议具体动作**：{s['action']}")
        report_lines.append(f"- **预期效果**：{s['effect']}")
        report_lines.append("")
    
    # ===== 十、总结 =====
    report_lines.append("## 十、总结")
    report_lines.append("")
    report_lines.append("```")
    
    # 健康度评估
    health = '🟢 优秀' if (len(active_with_sales) / total_active > 0.3 and total_gmv > 30000) else \
             ('🟡 中等' if (len(active_with_sales) / total_active > 0.1) else '🔴 较差')
    report_lines.append(f"商品健康度：{health}（{len(active_with_sales)}/{total_active} 商品有出单）")
    
    if sorted_products:
        top_pct = sorted_products[0]['gmv'] / total_gmv * 100 if total_gmv > 0 else 0
        report_lines.append(f"爆款表现：  {'🟢 优秀' if top_pct < 60 else '🟡 依赖度高'}（Top 1 占 {top_pct:.1f}%）")
    
    if new_products:
        report_lines.append(f"新品潜力：  🟢 良好（{len(new_products)} 款新品有出单）")
    
    if len(zero_data) > 5:
        report_lines.append(f"风险提示：  🔴 零数据商品过多（{len(zero_data)} 款）")
    
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
    
    # 文件名：商品数据分析_店铺_开始日期-结束日期.md
    date_str = w_latest['week_start'].replace('-', '')
    if w_previous:
        date_str = w_previous['week_start'].replace('-', '') + '-' + w_latest['week_end'].replace('-', '')
    
    filename = f"商品数据分析_{shop_code}_{date_str}.md"
    filepath = os.path.join(REPORT_DIR, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    
    print(f'[OK] 报告已生成: {filepath}')
    print(f'     商品: {total_active} 款在售, {len(active_with_sales)} 款有出单')
    print(f'     GMV: PHP {total_gmv:,.2f}')
    print(f'     建议: {len(suggestions)} 条')
    
    conn.close()
    return filepath

if __name__ == '__main__':
    shop_code = sys.argv[1] if len(sys.argv) > 1 else 'PNB'
    weeks = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    generate_report(shop_code, weeks)
