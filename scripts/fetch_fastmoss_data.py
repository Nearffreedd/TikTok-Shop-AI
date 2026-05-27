"""
Fastmoss 行业数据抓取脚本（requests 方式）
============================================
使用 requests 直接调用 Fastmoss API 获取销量榜数据。

用法：
  python scripts/fetch_fastmoss_data.py                          # 抓取默认类目（首饰）
  python scripts/fetch_fastmoss_data.py --category 8              # 指定类目ID
  python scripts/fetch_fastmoss_data.py --all                     # 抓取多个类目
  python scripts/fetch_fastmoss_data.py --report-only             # 仅基于已有数据生成报告
"""

import os
import sys
import json
import sqlite3
from datetime import datetime, timedelta

try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, 'scripts')
DB_PATH = os.path.join(BASE_DIR, 'Layer1_Permanent', '01_My_Shop', 'shop_data.db')
COOKIE_FILE = os.path.join(SCRIPTS_DIR, 'fastmoss_cookies.json')
INDUSTRY_DIR = os.path.join(BASE_DIR, 'Layer1_Permanent', '04_Industry')

CATEGORIES = {
    "8": "珠宝首饰及配件",
    "1": "女装",
    "2": "男装",
    "3": "美妆个护",
    "4": "3C数码",
    "5": "家居生活",
    "6": "母婴用品",
    "7": "运动户外",
}


def get_current_week_range():
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday.strftime('%Y-%m-%d'), sunday.strftime('%Y-%m-%d')


def get_week_number():
    today = datetime.now()
    iso = today.isocalendar()
    return f"{iso[0]}-{iso[1]:02d}"


def ensure_db_tables():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS industry_saleslist (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id TEXT NOT NULL,
            category_name TEXT,
            week_start TEXT NOT NULL,
            week_end TEXT NOT NULL,
            rank INTEGER,
            product_name TEXT,
            product_id TEXT,
            shop_name TEXT,
            shop_id TEXT,
            price_range TEXT,
            price_min REAL,
            price_max REAL,
            total_sales TEXT,
            total_gmv TEXT,
            sales_count INTEGER,
            gmv_amount REAL,
            commission_rate TEXT,
            source_file TEXT,
            raw_json TEXT,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(category_id, week_start, week_end, rank)
        )
    ''')
    conn.commit()
    conn.close()
    print("[OK] 行业数据表已就绪")


def fetch_saleslist(category_id="8", pagesize=50):
    """使用 requests 直接调用 Fastmoss API 获取销量榜数据"""
    import requests

    week_start, week_end = get_current_week_range()

    print(f"\n[抓取] 正在抓取类目 [{CATEGORIES.get(category_id, '未知')}] (ID={category_id})...")

    if not os.path.exists(COOKIE_FILE):
        print(f"[错误] Cookie 文件不存在: {COOKIE_FILE}")
        return []

    with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
        cookies_list = json.load(f)
    cookies_dict = {c['name']: c['value'] for c in cookies_list}

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://www.fastmoss.com/zh/e-commerce/saleslist',
        'Origin': 'https://www.fastmoss.com',
    }

    all_products = []

    # 抓取日榜
    params = {
        'page': '1',
        'pagesize': str(pagesize),
        'order': '1,2',
        'region': 'PH',
        'l1_cid': category_id,
        'date_type': '1',  # 日榜
    }
    resp = requests.get(
        'https://www.fastmoss.com/api/goods/saleRank',
        params=params,
        cookies=cookies_dict,
        headers=headers,
        timeout=15
    )
    data = resp.json()

    if data.get('code') != 200:
        print(f"   [错误] API 返回: {data.get('code')} - {data.get('msg')}")
        return []

    rank_list = data.get('data', {}).get('rank_list', [])
    print(f"   日榜: {len(rank_list)} 个商品")

    for i, item in enumerate(rank_list):
        product = parse_product(item, i + 1)
        all_products.append(product)

    # 抓取周榜
    week_label = get_week_number()
    params['date_type'] = '2'  # 周榜
    params['date_value'] = week_label
    resp = requests.get(
        'https://www.fastmoss.com/api/goods/saleRank',
        params=params,
        cookies=cookies_dict,
        headers=headers,
        timeout=15
    )
    data = resp.json()

    if data.get('code') == 200:
        rank_list = data.get('data', {}).get('rank_list', [])
        print(f"   周榜: {len(rank_list)} 个商品")
        for i, item in enumerate(rank_list):
            product = parse_product(item, i + 1)
            all_products.append(product)

    # 去重
    seen = set()
    unique_products = []
    for p in all_products:
        pid = p.get('product_id', '')
        if pid and pid not in seen:
            seen.add(pid)
            unique_products.append(p)

    print(f"   [结果] 共获取到 {len(unique_products)} 个唯一商品")
    return unique_products


def parse_product(item, rank):
    """解析单个商品数据"""
    product = {
        'rank': rank,
        'product_id': str(item.get('product_id', '')),
        'product_name': item.get('title', ''),
        'shop_name': item.get('shop_name', ''),
        'shop_id': str(item.get('shop_id', '')),
        'price_range': item.get('real_price', ''),
        'price_min': None,
        'price_max': None,
        'total_sales': str(item.get('total_sold_count', '')),
        'total_gmv': str(item.get('total_sale_amount', '')),
        'sales_count': item.get('sold_count', 0),
        'gmv_amount': item.get('sale_amount', 0),
        'commission_rate': item.get('commission_rate', ''),
    }

    # 解析价格
    price = item.get('real_price', '')
    if price:
        import re
        nums = re.findall(r'[\d.]+', price.replace(',', ''))
        if len(nums) >= 2:
            product['price_min'] = float(nums[0])
            product['price_max'] = float(nums[1])
        elif len(nums) == 1:
            product['price_min'] = float(nums[0])
            product['price_max'] = float(nums[0])

    return product


def save_to_database(products, category_id):
    week_start, week_end = get_current_week_range()
    category_name = CATEGORIES.get(category_id, f"类目_{category_id}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    saved_count = 0
    for i, product in enumerate(products):
        rank = i + 1
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO industry_saleslist
                (category_id, category_name, week_start, week_end, rank,
                 product_name, product_id, shop_name, shop_id, price_range,
                 price_min, price_max, total_sales, total_gmv,
                 sales_count, gmv_amount, commission_rate, source_file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                category_id, category_name, week_start, week_end, rank,
                product['product_name'][:500], product['product_id'],
                product['shop_name'][:200], product['shop_id'],
                product['price_range'][:100],
                product['price_min'], product['price_max'],
                product['total_sales'][:50], product['total_gmv'][:50],
                product['sales_count'], product['gmv_amount'],
                product['commission_rate'],
                f'fastmoss_api_{week_start}'
            ))
            saved_count += 1
        except Exception as e:
            print(f"   [警告] 保存失败 (rank={rank}): {e}")

    conn.commit()
    conn.close()
    print(f"   [保存] 已保存 {saved_count} 条记录到数据库")
    return saved_count


def generate_industry_report(category_id="8"):
    week_start, week_end = get_current_week_range()
    category_name = CATEGORIES.get(category_id, f"类目_{category_id}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT rank, product_name, shop_name, price_range, total_sales, total_gmv,
               sales_count, gmv_amount, commission_rate
        FROM industry_saleslist
        WHERE category_id = ? AND week_start = ?
        ORDER BY rank
        LIMIT 50
    ''', (category_id, week_start))
    weekly_data = cursor.fetchall()

    conn.close()

    today = datetime.now().strftime('%Y%m%d')
    report_path = os.path.join(INDUSTRY_DIR, f'行业趋势周报_{category_name}_{today}.md')
    os.makedirs(os.path.dirname(report_path), exist_ok=True)

    lines = [
        f"# 行业趋势周报：{category_name}",
        f"",
        f"- **抓取时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- **数据周期**: {week_start} ~ {week_end}",
        f"- **数据来源**: Fastmoss 销量榜 API",
        f"- **类目ID**: {category_id}",
        f"",
        f"## Top 50 热销商品",
        f"",
        f"| 排名 | 商品名称 | 店铺 | 价格区间 | 佣金率 | 日销量 | 日GMV | 总销量 | 总GMV |",
        f"|:---:|:---|:---|:---|:---:|:---:|:---:|:---:|:---:|",
    ]

    for row in weekly_data:
        rank, name, shop, price, ts, tg, s_count, g_amount, comm = row
        name_display = (name or '未知')[:40]
        shop_display = (shop or '未知')[:20]
        sales_display = f"{s_count:,}" if s_count else '-'
        gmv_display = f"₱{g_amount:,.0f}" if g_amount else '-'
        total_sales_display = ts or '-'
        total_gmv_display = tg or '-'
        lines.append(f"| {rank} | {name_display} | {shop_display} | {price or '-'} | {comm or '-'} | {sales_display} | {gmv_display} | {total_sales_display} | {total_gmv_display} |")

    if not weekly_data:
        lines.append(f"| — | 暂无数据 | — | — | — | — | — | — | — |")

    lines.extend([
        f"",
        f"---",
        f"",
        f"## 分析摘要",
        f"",
        f"> 此报告由 `scripts/fetch_fastmoss_data.py` 自动生成",
        f"> 数据仅供参考，建议结合手动调研验证",
    ])

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"\n[报告] 行业趋势报告已生成: {report_path}")
    return report_path


def fetch_all_categories():
    results = {}
    for cid in ["1", "3", "8"]:
        products = fetch_saleslist(category_id=cid)
        if products:
            save_to_database(products, cid)
            results[cid] = len(products)
        else:
            print(f"   [警告] 类目 {cid} 未获取到数据")
    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Fastmoss 行业数据抓取工具')
    parser.add_argument('--category', default='8', help='类目ID (8=珠宝首饰, 1=女装, 3=美妆)')
    parser.add_argument('--all', action='store_true', help='抓取所有主要类目')
    parser.add_argument('--report-only', action='store_true', help='仅基于已有数据生成报告，不抓取')
    args = parser.parse_args()

    print(f"""
+===============================================+
|     Fastmoss 行业数据抓取工具                  |
|                                                 |
|     数据源: https://www.fastmoss.com           |
|     数据库: {os.path.basename(DB_PATH)}
|     方式: requests 直接调用 API
+===============================================+
""")

    ensure_db_tables()

    if args.report_only:
        generate_industry_report(args.category)
        return

    if args.all:
        results = fetch_all_categories()
        print(f"\n{'='*50}")
        print("  抓取完成!")
        for cid, count in results.items():
            print(f"  - {CATEGORIES.get(cid, cid)}: {count} 条")
        for cid in results:
            generate_industry_report(cid)
    else:
        products = fetch_saleslist(category_id=args.category)
        if products:
            save_to_database(products, args.category)
            generate_industry_report(args.category)
        else:
            print(f"\n[警告] 类目 {args.category} 未抓取到数据")


if __name__ == '__main__':
    main()
