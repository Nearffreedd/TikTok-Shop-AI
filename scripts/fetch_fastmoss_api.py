"""
Fastmoss API 数据抓取脚本
============================
使用 Playwright 拦截 Fastmoss 的内部 API 请求，获取行业数据

Fastmoss 是 Next.js App Router 应用，数据通过客户端 JS 动态请求 API 获取。
本脚本通过 Playwright 打开页面，拦截 XHR/fetch 请求来捕获 API 响应数据。

用法：
  python scripts/fetch_fastmoss_api.py                          # 抓取默认类目（首饰）
  python scripts/fetch_fastmoss_api.py --category 8              # 指定类目ID
  python scripts/fetch_fastmoss_api.py --all                     # 抓取多个类目
  python scripts/fetch_fastmoss_api.py --report-only             # 仅基于已有数据生成报告
"""

import os
import sys
import json
import re
import sqlite3
import requests
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

# 解决 Windows 终端编码问题
try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, 'scripts')
DB_PATH = os.path.join(BASE_DIR, 'Layer1_Permanent', '01_My_Shop', 'shop_data.db')
COOKIE_FILE = os.path.join(SCRIPTS_DIR, 'fastmoss_cookies.json')
INDUSTRY_DIR = os.path.join(BASE_DIR, 'Layer1_Permanent', '04_Industry')

# Fastmoss 类目映射（菲律宾站）
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

DATE_TYPE_WEEKLY = "2"


def get_current_week_range():
    """获取当前周的起止日期"""
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday.strftime('%Y-%m-%d'), sunday.strftime('%Y-%m-%d')


def get_week_number():
    """获取当前周数 (YYYY-WW)"""
    today = datetime.now()
    iso = today.isocalendar()
    return f"{iso[0]}-{iso[1]:02d}"


def ensure_db_tables():
    """确保行业数据表存在"""
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
            source_file TEXT,
            raw_json TEXT,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(category_id, week_start, week_end, rank)
        )
    ''')

    conn.commit()
    conn.close()
    print("[OK] 行业数据表已就绪")


def load_cookies_as_dict():
    """从 Cookie 文件加载并转换为 dict 格式"""
    if not os.path.exists(COOKIE_FILE):
        print(f"[错误] Cookie 文件不存在: {COOKIE_FILE}")
        print("   请先运行: python scripts/fastmoss_login_and_fetch.py")
        return None

    with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
        cookies_list = json.load(f)

    cookies_dict = {}
    for c in cookies_list:
        cookies_dict[c['name']] = c['value']
    return cookies_dict


def fetch_saleslist_via_api(category_id="8"):
    """
    直接调用 Fastmoss API 获取销量榜数据
    不需要 Playwright 浏览器，直接用 requests
    """
    week_start, week_end = get_current_week_range()
    week_label = get_week_number()

    print(f"\n[抓取] 正在抓取类目 [{CATEGORIES.get(category_id, '未知')}] (ID={category_id})...")

    cookies_dict = load_cookies_as_dict()
    if not cookies_dict:
        return []

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://www.fastmoss.com/zh/e-commerce/saleslist',
        'Origin': 'https://www.fastmoss.com',
    }

    # 尝试日榜和周榜
    all_products = []
    for date_type, date_label, date_desc in [
        ("1", "", "日榜"),
        ("2", week_label, "周榜"),
    ]:
        params = {
            'page': '1',
            'pagesize': '20',
            'order': '1,2',
            'region': 'PH',
            'l1_cid': category_id,
            'date_type': date_type,
        }
        if date_label:
            params['date_value'] = date_label

        api_url = "https://www.fastmoss.com/api/goods/saleRank"
        print(f"   [{date_desc}] 请求 API...")

        try:
            resp = requests.get(api_url, params=params, cookies=cookies_dict, headers=headers, timeout=30)
            if resp.status_code != 200:
                print(f"   [{date_desc}] HTTP {resp.status_code}")
                continue

            raw_data = resp.json()

            # 处理可能的列表/字典类型不一致
            if isinstance(raw_data, list):
                # 如果返回的是列表，直接解析
                print(f"   [{date_desc}] 返回列表类型 ({len(raw_data)} items)，直接解析...")
                for i, item in enumerate(raw_data):
                    if isinstance(item, dict):
                        product = {
                            'rank': i + 1,
                            'product_id': str(item.get('product_id', '')),
                            'product_name': item.get('product_name', item.get('title', '')),
                            'shop_name': item.get('shop_name', ''),
                            'shop_id': str(item.get('shop_id', '')),
                            'price_range': '',
                            'price_min': None,
                            'price_max': None,
                            'total_sales': str(item.get('sold_count', '')),
                            'total_gmv': str(item.get('sale_amount', '')),
                            'sales_count': item.get('sold_count', 0),
                            'gmv_amount': item.get('sale_amount', 0),
                            'date_type': date_type,
                        }
                        all_products.append(product)
                continue

            # 标准响应格式: {"code":200, "data":{...}, "msg":"success"}
            if not isinstance(raw_data, dict):
                print(f"   [{date_desc}] 未知响应类型: {type(raw_data).__name__}")
                continue

            data = raw_data
            if data.get('code') != 200:
                print(f"   [{date_desc}] API 错误: {data.get('msg', 'unknown')}")
                continue

            # data 字段可能是 dict 或 list
            data_field = data.get('data', {})
            if isinstance(data_field, list):
                # data 字段直接是列表
                print(f"   [{date_desc}] data 字段是列表 ({len(data_field)} items)")
                for i, item in enumerate(data_field):
                    if isinstance(item, dict):
                        product = {
                            'rank': i + 1,
                            'product_id': str(item.get('product_id', '')),
                            'product_name': item.get('product_name', item.get('title', '')),
                            'shop_name': item.get('shop_name', ''),
                            'shop_id': str(item.get('shop_id', '')),
                            'price_range': '',
                            'price_min': None,
                            'price_max': None,
                            'total_sales': str(item.get('sold_count', '')),
                            'total_gmv': str(item.get('sale_amount', '')),
                            'sales_count': item.get('sold_count', 0),
                            'gmv_amount': item.get('sale_amount', 0),
                            'date_type': date_type,
                        }
                        all_products.append(product)
                continue

            rank_list = data_field.get('rank_list', [])
            total_count = data.get('data', {}).get('total_count', 0)
            print(f"   [{date_desc}] 获取到 {len(rank_list)} 条数据 (总计: {total_count})")

            for i, item in enumerate(rank_list):
                product = {
                    'rank': i + 1,
                    'product_id': str(item.get('product_id', '')),
                    'product_name': item.get('product_name', item.get('title', '')),
                    'shop_name': item.get('shop_name', item.get('shopName', '')),
                    'shop_id': str(item.get('shop_id', item.get('shopId', ''))),
                    'price_range': '',
                    'price_min': None,
                    'price_max': None,
                    'total_sales': str(item.get('sold_count', item.get('total_sold_count', ''))),
                    'total_gmv': str(item.get('sale_amount', item.get('total_sale_amount', ''))),
                    'sales_count': item.get('sold_count', 0),
                    'gmv_amount': item.get('sale_amount', 0),
                    'date_type': date_type,
                }

                # 处理价格
                price = item.get('price', item.get('priceRange', ''))
                if isinstance(price, (int, float)):
                    product['price_min'] = float(price)
                    product['price_max'] = float(price)
                    product['price_range'] = f"₱{price}"
                elif isinstance(price, dict):
                    product['price_min'] = price.get('min', price.get('low', 0))
                    product['price_max'] = price.get('max', price.get('high', 0))
                    product['price_range'] = f"₱{product['price_min']} - ₱{product['price_max']}"

                if product['product_name'] or product['product_id']:
                    all_products.append(product)

        except Exception as e:
            import traceback
            print(f"   [{date_desc}] 请求失败: {e}")
            traceback.print_exc()

    # 去重（按 product_id）
    seen = set()
    unique_products = []
    for p in all_products:
        pid = p.get('product_id', '')
        if pid and pid not in seen:
            seen.add(pid)
            unique_products.append(p)

    print(f"   [结果] 共获取到 {len(unique_products)} 个唯一商品")
    return unique_products


def parse_api_response(body, url):
    """解析 API 响应中的商品数据"""
    products = []

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return products

    # 尝试多种数据路径
    records = None

    # 路径1: data.records (Ant Design Table 格式)
    if isinstance(data, dict):
        records = data.get('data', {}).get('records', None)

    # 路径2: data.list
    if not records and isinstance(data, dict):
        records = data.get('data', {}).get('list', None)

    # 路径3: data.items
    if not records and isinstance(data, dict):
        records = data.get('data', {}).get('items', None)

    # 路径4: data 本身就是列表
    if not records and isinstance(data, dict):
        if isinstance(data.get('data'), list):
            records = data['data']

    # 路径5: 直接是列表
    if not records and isinstance(data, list):
        records = data

    # 路径6: data.rows
    if not records and isinstance(data, dict):
        records = data.get('data', {}).get('rows', None)

    # 路径7: data.result
    if not records and isinstance(data, dict):
        records = data.get('data', {}).get('result', None)

    # 路径8: data.rank_list (Fastmoss 销量榜 API)
    if not records and isinstance(data, dict):
        records = data.get('data', {}).get('rank_list', None)

    if not records:
        return products

    for i, item in enumerate(records):
        if not isinstance(item, dict):
            continue

        product = {
            'rank': i + 1,
            'product_name': item.get('productName', item.get('product_name', item.get('title', item.get('name', '')))),
            'product_id': str(item.get('productId', item.get('product_id', item.get('id', '')))),
            'shop_name': item.get('shopName', item.get('shop_name', item.get('shop', ''))),
            'shop_id': str(item.get('shopId', item.get('shop_id', ''))),
            'price_range': '',
            'price_min': None,
            'price_max': None,
            'total_sales': str(item.get('totalSales', item.get('total_sales', item.get('sales', '')))),
            'total_gmv': str(item.get('totalGmv', item.get('total_gmv', item.get('gmv', '')))),
            'sales_count': item.get('salesCount', item.get('sales_count', 0)),
            'gmv_amount': item.get('gmvAmount', item.get('gmv_amount', 0)),
        }

        # 处理价格
        price = item.get('price', item.get('priceRange', item.get('price_range', '')))
        if isinstance(price, (int, float)):
            product['price_min'] = float(price)
            product['price_max'] = float(price)
            product['price_range'] = f"₱{price}"
        elif isinstance(price, dict):
            product['price_min'] = price.get('min', price.get('low', 0))
            product['price_max'] = price.get('max', price.get('high', 0))
            product['price_range'] = f"₱{product['price_min']} - ₱{product['price_max']}"
        elif isinstance(price, str):
            product['price_range'] = price

        # 清理空值
        for k, v in list(product.items()):
            if v is None:
                product[k] = '' if k in ['product_name', 'shop_name', 'price_range', 'total_sales', 'total_gmv'] else 0

        if product['product_name']:
            products.append(product)

    return products


def save_to_database(products, category_id):
    """将抓取的数据存入数据库"""
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
                 sales_count, gmv_amount, source_file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                category_id, category_name, week_start, week_end, rank,
                product['product_name'][:200], product['product_id'],
                product['shop_name'][:100], product['shop_id'],
                product['price_range'][:100],
                product['price_min'], product['price_max'],
                product['total_sales'][:50], product['total_gmv'][:50],
                product['sales_count'], product['gmv_amount'],
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
    """从数据库读取数据，生成行业趋势报告"""
    week_start, week_end = get_current_week_range()
    category_name = CATEGORIES.get(category_id, f"类目_{category_id}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT rank, product_name, shop_name, price_range, total_sales, total_gmv, sales_count, gmv_amount
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
        f"- **数据来源**: Fastmoss 销量榜 (API)",
        f"- **类目ID**: {category_id}",
        f"",
        f"## Top 50 热销商品",
        f"",
        f"| 排名 | 商品名称 | 店铺 | 价格区间 | 总销量 | 总GMV |",
        f"|:---:|:---|:---|:---|:---:|:---:|",
    ]

    for row in weekly_data:
        rank, name, shop, price, sales, gmv, s_count, g_amount = row
        name_display = (name or '未知')[:35]
        shop_display = (shop or '未知')[:20]
        sales_display = sales or (f"{s_count:,}" if s_count else '-')
        gmv_display = gmv or (f"₱{g_amount:,.0f}" if g_amount else '-')
        lines.append(f"| {rank} | {name_display} | {shop_display} | {price or '-'} | {sales_display} | {gmv_display} |")

    if not weekly_data:
        lines.append(f"| — | 暂无数据 | — | — | — | — |")

    lines.extend([
        f"",
        f"---",
        f"",
        f"## 分析摘要",
        f"",
        f"> 此报告由 `scripts/fetch_fastmoss_api.py` 自动生成",
        f"> 数据仅供参考，建议结合手动调研验证",
    ])

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"\n[报告] 行业趋势报告已生成: {report_path}")
    return report_path


def fetch_all_categories():
    """抓取所有主要类目的数据"""
    results = {}
    for cid in ["1", "3", "8"]:
        products = fetch_saleslist_via_api(category_id=cid)
        if products:
            save_to_database(products, cid)
            results[cid] = len(products)
        else:
            print(f"   [警告] 类目 {cid} 未获取到数据")
    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Fastmoss API 数据抓取工具')
    parser.add_argument('--category', default='8', help='类目ID (8=珠宝首饰, 1=女装, 3=美妆)')
    parser.add_argument('--all', action='store_true', help='抓取所有主要类目')
    parser.add_argument('--report-only', action='store_true', help='仅基于已有数据生成报告，不抓取')
    args = parser.parse_args()

    print(f"""
+===============================================+
|     Fastmoss API 数据抓取工具                   |
|                                                 |
|     数据源: https://www.fastmoss.com           |
|     数据库: {os.path.basename(DB_PATH)}
|     方式: Playwright 拦截 API 请求
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
        products = fetch_saleslist_via_api(category_id=args.category)
        if products:
            save_to_database(products, args.category)
            generate_industry_report(args.category)
        else:
            print(f"\n[警告] 类目 {args.category} 未抓取到数据")
            print("   可能原因:")
            print("   1. Cookie 已过期 - 请重新登录 Fastmoss 并更新 Cookie")
            print("   2. API 路径变更 - 请检查拦截到的请求")
            print("   3. 触发了反爬虫验证")


if __name__ == '__main__':
    main()
