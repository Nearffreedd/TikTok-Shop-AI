"""
GMV MAX 广告投放数据导入脚本
功能：读取 Product campaign data Excel -> 解析广告名称 -> 写入 SQLite 数据库
用法：python import_gmvmax.py <Excel文件路径> [店铺代码]

文件名格式：
  [店铺名] Product campaign data YYYY-MM-DD - YYYY-MM-DD.xlsx
  如：PNB Product campaign data 2026-05-11 - 2026-05-17.xlsx
  向后兼容：Product campaign data YYYY-MM-DD - YYYY-MM-DD.xlsx

广告名称解析规则：
  ST01-20260421-roi 6.5          -> 产品:ST01, 日期:20260421, 目标ROI:6.5
  MJ01&SL06-20260512-ROI 2.9     -> 联投:MJ01+SL06, 目标ROI:2.9
  20260318/SL06/ROI 3/预算200    -> 产品:SL06, 目标ROI:3, 预算:200
  ROI 4.9                        -> 仅有目标ROI
  Other product                  -> 标记为"其他通用计划"
"""

import sqlite3
import openpyxl
import os
import sys
import re
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'Layer1_Permanent', '01_My_Shop', 'shop_data.db')

# 已知产品代码列表（用于名称解析）
KNOWN_PRODUCT_CODES = ['ST01', 'SL06', 'SL07', 'MJ01', 'FQ01', 'SL01', 'ST04']


def parse_week_range_from_filename(filename):
    """从文件名解析周范围
    如 'PNB Product campaign data 2026-05-11 - 2026-05-17.xlsx'
       -> ('2026-05-11', '2026-05-17')
    也支持 'Product campaign data 2026-05-11 - 2026-05-17.xlsx'
    """
    match = re.search(r'(\d{4}-\d{2}-\d{2})\s*-\s*(\d{4}-\d{2}-\d{2})', filename)
    if match:
        return match.group(1), match.group(2)
    return None, None


def detect_shop_code(filename):
    """从文件名识别店铺代码
    如 'PNB Product campaign data...' -> 'PNB'
    无前缀则返回 None
    """
    match = re.match(r'^([A-Z]+)\s+Product campaign data', filename)
    if match:
        return match.group(1)
    return None


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


def parse_campaign_name(name):
    """解析广告计划名称，提取结构化信息
    返回: (product_code, product_code2, target_roi, extracted_budget)
    """
    if not name:
        return None, None, None, None

    name = name.strip()

    # 特殊处理：Other product
    if name == 'Other product':
        return 'OTHER', None, None, None

    product_code = None
    product_code2 = None
    target_roi = None
    extracted_budget = None

    # ---- 格式1: ST01-20260421-roi 6.5 ----
    # 匹配产品代码（可能联投 MJ01&SL06）
    code_match = re.match(r'^([A-Z0-9]+)(?:&([A-Z0-9]+))?[-_]', name)
    if code_match:
        c1 = code_match.group(1)
        c2 = code_match.group(2)
        if c1 in KNOWN_PRODUCT_CODES:
            product_code = c1
            if c2 and c2 in KNOWN_PRODUCT_CODES:
                product_code2 = c2

    # ---- 格式2: 20260318/SL06/ROI 3/预算200 ----
    if not product_code:
        slash_match = re.search(r'/([A-Z0-9]+)/', name)
        if slash_match:
            c = slash_match.group(1)
            if c in KNOWN_PRODUCT_CODES:
                product_code = c

    # ---- 格式3: 20260307 / SL01 / ROI 2/ 预算40 ----
    if not product_code:
        space_match = re.search(r'/\s*([A-Z0-9]+)\s*/', name)
        if space_match:
            c = space_match.group(1)
            if c in KNOWN_PRODUCT_CODES:
                product_code = c

    # ---- 提取目标 ROI ----
    roi_match = re.search(r'ROI\s*[:\s]*([\d.]+)', name, re.IGNORECASE)
    if roi_match:
        target_roi = float(roi_match.group(1))

    # ---- 提取预算 ----
    budget_match = re.search(r'预算\s*([\d.]+)', name)
    if budget_match:
        extracted_budget = float(budget_match.group(1))

    return product_code, product_code2, target_roi, extracted_budget


def import_gmvmax(filepath, shop_code=None):
    """导入 GMV MAX 广告投放数据"""
    if not os.path.exists(filepath):
        print(f'[X] 文件不存在: {filepath}')
        return False

    filename = os.path.basename(filepath)

    # 从文件名解析周范围
    week_start, week_end = parse_week_range_from_filename(filename)
    if week_start is None:
        print(f'[X] 无法从文件名解析日期范围: {filename}')
        return False

    # 自动识别店铺代码
    if shop_code is None:
        shop_code = detect_shop_code(filename)
        if shop_code is None:
            print('[WARN] 无法从文件名识别店铺代码，使用默认 PNB')
            shop_code = 'PNB'

    print(f'[文件] {filename}')
    print(f'[店铺] {shop_code}')
    print(f'[周期] {week_start} ~ {week_end}')

    # 读取 Excel
    wb = openpyxl.load_workbook(filepath)
    ws = wb.active

    # 第1行是表头
    headers = [str(c.value).strip() if c.value else '' for c in ws[1]]

    # 连接数据库
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    stats = {
        'imported': 0,
        'updated': 0,
        'skipped': 0,
        'errors': 0,
    }

    # 遍历数据行（从第2行开始）
    for row_idx, row_data in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if row_data[0] is None:
            continue

        d = dict(zip(headers, row_data))

        campaign_id = str(d.get('广告计划 ID', '')).strip()
        campaign_name = str(d.get('广告计划名称', '')).strip()

        if not campaign_id or campaign_id == 'None':
            stats['skipped'] += 1
            continue

        # 解析数值
        cost = parse_float(d.get('成本'))
        roi_protection = str(d.get('ROI 保护', '')).strip()
        net_cost = parse_float(d.get('净成本'))
        current_budget = parse_float(d.get('当前预算'))
        sku_orders = parse_int(d.get('SKU 订单数'))
        avg_order_cost = parse_float(d.get('平均下单成本'))
        total_revenue = parse_float(d.get('总收入'))
        roi = parse_float(d.get('ROI'))
        currency = str(d.get('货币', 'USD')).strip()
        optimization_mode = str(d.get('当前优化模式', '')).strip()

        # 解析广告名称
        product_code, product_code2, target_roi, extracted_budget = parse_campaign_name(campaign_name)

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO gmvmax_campaign_weekly (
                    campaign_id, campaign_name, week_start, week_end,
                    product_code, product_code2, target_roi, extracted_budget,
                    cost, net_cost, current_budget, sku_orders, avg_order_cost,
                    total_revenue, roi, currency, roi_protection, optimization_mode,
                    source_file
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                campaign_id, campaign_name, week_start, week_end,
                product_code, product_code2, target_roi, extracted_budget,
                cost, net_cost, current_budget, sku_orders, avg_order_cost,
                total_revenue, roi, currency, roi_protection, optimization_mode,
                filename
            ))
            stats['imported'] += 1

        except Exception as e:
            print(f'  [WARN] 行 {row_idx} 导入失败: {e}')
            stats['errors'] += 1

    conn.commit()
    conn.close()

    print(f'[完成] 导入统计:')
    print(f'       新增/更新: {stats["imported"]}')
    print(f'       跳过:      {stats["skipped"]}')
    print(f'       错误:      {stats["errors"]}')
    return True


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python import_gmvmax.py <Excel文件路径> [店铺代码]')
        print('示例:')
        print('  python import_gmvmax.py "Layer2_Working/GMV MAX Product campaign data 2026-05-11 - 2026-05-17.xlsx"')
        print('  python import_gmvmax.py "Layer2_Working/PNB Product campaign data 2026-05-18 - 2026-05-24.xlsx" PNB')
        sys.exit(1)

    filepath = sys.argv[1]
    shop_code = sys.argv[2] if len(sys.argv) > 2 else None

    if not os.path.isabs(filepath):
        filepath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), filepath)

    import_gmvmax(filepath, shop_code)
