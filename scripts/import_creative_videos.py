"""
创意视频数据导入脚本
功能：读取 Creatives video data Excel -> 写入 SQLite 数据库（3 张表）
用法：python import_creative_videos.py <Excel文件路径>

数据规则：
- 第1行：中文表头（视频ID、商品ID、视频标题、用户名...）
- 第3行：英文表头（实际用于映射）
- 第4行起：数据行
- 周范围从文件名解析（如 "Creatives video data 20260511 - 20260517.xlsx"）

表结构：
  video_creatives      - 视频主表（去重）
  video_product_link   - 视频↔商品关联
  video_weekly_perf    - 视频周表现
"""

import sqlite3
import openpyxl
import os
import sys
import re
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'Layer1_Permanent', '01_My_Shop', 'shop_data.db')

# 中文表头 -> 内部字段名映射
HEADER_MAP = {
    '视频 ID': 'video_id',
    '商品 ID': 'product_id',
    '视频标题': 'video_title',
    '用户名': 'username',
    '商品名称': 'product_name',
    '授权类型': 'auth_type',
    '授权状态': 'auth_status',
    '总收入': 'revenue',
    '发布时间': 'publish_date',
    'SKU 订单数': 'sku_orders',
    '成本': 'cost',
    '平均下单成本': 'avg_order_cost',
    'ROI': 'roi',
    '商品广告曝光数': 'ad_impressions',
    '商品广告点击数': 'ad_clicks',
    '商品广告点击率': 'ad_ctr',
    '广告转化率': 'ad_cvr',
    '广告视频 2 秒播放率': 'play_2s',
    '广告视频 6 秒播放率': 'play_6s',
    '标签': 'tag',
    '预审核状态': 'review_status',
    '视频来源': 'video_source',
    '币种': 'currency',
}


def parse_week_range_from_filename(filename):
    """从文件名解析周范围
    如 'Creatives video data 20260511 - 20260517.xlsx' -> ('2026-05-11', '2026-05-17')
    """
    match = re.search(r'(\d{8})\s*-\s*(\d{8})', filename)
    if match:
        start = datetime.strptime(match.group(1), '%Y%m%d').strftime('%Y-%m-%d')
        end = datetime.strptime(match.group(2), '%Y%m%d').strftime('%Y-%m-%d')
        return start, end
    return None, None


def parse_float(val):
    """安全解析数值"""
    if val is None or val == '' or val == '-':
        return 0.0
    try:
        s = str(val).strip().replace(',', '').replace('$', '').replace('USD', '').strip()
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def parse_int(val):
    """安全解析整数"""
    if val is None or val == '' or val == '-':
        return 0
    try:
        return int(float(str(val).strip().replace(',', '')))
    except (ValueError, TypeError):
        return 0


def parse_pct(val):
    """安全解析百分比（Excel 中可能是小数或百分比字符串）"""
    if val is None or val == '' or val == '-':
        return 0.0
    try:
        s = str(val).strip().replace('%', '').strip()
        v = float(s)
        # 如果大于 1，说明是百分比数值（如 38.07），需要除以 100
        if v > 1:
            return v / 100
        return v
    except (ValueError, TypeError):
        return 0.0


def import_creative_videos(filepath):
    """导入创意视频数据"""
    if not os.path.exists(filepath):
        print(f'[X] 文件不存在: {filepath}')
        return False

    filename = os.path.basename(filepath)

    # 从文件名解析周范围
    week_start, week_end = parse_week_range_from_filename(filename)
    if week_start is None:
        print(f'[X] 无法从文件名解析日期范围: {filename}')
        return False

    print(f'[文件] {filename}')
    print(f'[周期] {week_start} ~ {week_end}')

    # 读取 Excel
    wb = openpyxl.load_workbook(filepath)
    ws = wb.active

    # 第1行是中文表头，第3行是英文表头（实际数据列）
    # 用第1行做映射
    cn_headers = [str(c.value).strip() if c.value else '' for c in ws[1]]

    # 连接数据库
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    stats = {
        'video_creatives': 0,
        'video_product_link': 0,
        'video_weekly_perf': 0,
        'skipped': 0,
        'errors': 0,
    }

    # 遍历数据行（从第4行开始）
    for row_idx, row_data in enumerate(ws.iter_rows(min_row=4, values_only=True), start=4):
        if row_data[0] is None:
            continue

        # 构建字段字典
        d = {}
        for i, val in enumerate(row_data):
            if i < len(cn_headers):
                field_name = HEADER_MAP.get(cn_headers[i])
                if field_name:
                    d[field_name] = val

        video_id = str(d.get('video_id', '')).strip()
        product_id = str(d.get('product_id', '')).strip()
        video_title = str(d.get('video_title', '')).strip()
        username = str(d.get('username', '')).strip()
        auth_type = str(d.get('auth_type', '')).strip()
        auth_status = str(d.get('auth_status', '')).strip()
        publish_date = str(d.get('publish_date', '')).strip()
        video_source = str(d.get('video_source', '')).strip()
        tag = str(d.get('tag', '')).strip()

        if not video_id:
            stats['skipped'] += 1
            continue

        # 解析数值
        revenue = parse_float(d.get('revenue'))
        sku_orders = parse_int(d.get('sku_orders'))
        cost = parse_float(d.get('cost'))
        avg_order_cost = parse_float(d.get('avg_order_cost'))
        roi = parse_float(d.get('roi'))
        ad_impressions = parse_int(d.get('ad_impressions'))
        ad_clicks = parse_int(d.get('ad_clicks'))
        ad_ctr = parse_pct(d.get('ad_ctr'))
        ad_cvr = parse_pct(d.get('ad_cvr'))
        play_2s = parse_pct(d.get('play_2s'))
        play_6s = parse_pct(d.get('play_6s'))

        try:
            # ===== 1. 写入 video_creatives（视频主表，去重） =====
            cursor.execute('''
                INSERT OR IGNORE INTO video_creatives (video_id, video_title, username, publish_date, video_source, first_seen_week, last_seen_week)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (video_id, video_title, username, publish_date, video_source, week_start, week_end))

            if cursor.rowcount > 0:
                stats['video_creatives'] += 1
            else:
                # 已存在，更新 last_seen_week
                cursor.execute('''
                    UPDATE video_creatives SET last_seen_week = ? WHERE video_id = ? AND last_seen_week < ?
                ''', (week_end, video_id, week_end))

            # ===== 2. 写入 video_product_link（视频↔商品关联） =====
            if product_id and product_id != 'None':
                cursor.execute('''
                    INSERT OR IGNORE INTO video_product_link (video_id, platform_product_id, authorization_type, authorization_status)
                    VALUES (?, ?, ?, ?)
                ''', (video_id, product_id, auth_type, auth_status))

                if cursor.rowcount > 0:
                    stats['video_product_link'] += 1

            # ===== 3. 写入 video_weekly_perf（视频周表现） =====
            cursor.execute('''
                INSERT OR REPLACE INTO video_weekly_perf (
                    video_id, week_start, week_end, platform_product_id,
                    revenue, sku_orders, cost, avg_order_cost, roi,
                    ad_impressions, ad_clicks, ad_ctr, ad_conversion_rate,
                    play_2s_rate, play_6s_rate, tag_label, source_file
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                video_id, week_start, week_end, product_id if product_id != 'None' else '0',
                revenue, sku_orders, cost, avg_order_cost, roi,
                ad_impressions, ad_clicks, ad_ctr, ad_cvr,
                play_2s, play_6s, tag, filename
            ))
            stats['video_weekly_perf'] += 1

        except Exception as e:
            print(f'  [WARN] 行 {row_idx} 导入失败: {e}')
            stats['errors'] += 1

    conn.commit()
    conn.close()

    print(f'[完成] 导入统计:')
    print(f'       视频主表新增: {stats["video_creatives"]}')
    print(f'       视频商品关联: {stats["video_product_link"]}')
    print(f'       视频周表现:   {stats["video_weekly_perf"]}')
    print(f'       跳过:         {stats["skipped"]}')
    print(f'       错误:         {stats["errors"]}')
    return True


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python import_creative_videos.py <Excel文件路径>')
        print('示例: python import_creative_videos.py "Layer2_Working/Creatives video data 20260511 - 20260517.xlsx"')
        sys.exit(1)

    filepath = sys.argv[1]
    if not os.path.isabs(filepath):
        filepath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), filepath)

    import_creative_videos(filepath)
