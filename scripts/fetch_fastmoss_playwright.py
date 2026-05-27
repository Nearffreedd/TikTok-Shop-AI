"""
Fastmoss Playwright 数据抓取脚本
===================================
使用 Playwright 浏览器打开 Fastmoss 页面，拦截 API 请求获取数据。
浏览器会自动处理安全验证（MSG_SAFE_0001），因为浏览器有完整的 JS 环境。

用法：
  python scripts/fetch_fastmoss_playwright.py                          # 抓取默认类目（首饰）
  python scripts/fetch_fastmoss_playwright.py --category 8              # 指定类目ID
  python scripts/fetch_fastmoss_playwright.py --all                     # 抓取多个类目
  python scripts/fetch_fastmoss_playwright.py --report-only             # 仅基于已有数据生成报告
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
            source_file TEXT,
            raw_json TEXT,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(category_id, week_start, week_end, rank)
        )
    ''')
    conn.commit()
    conn.close()
    print("[OK] 行业数据表已就绪")


def fetch_saleslist_via_playwright(category_id="8"):
    """
    使用 Playwright 打开 Fastmoss 销量榜页面，
    拦截 API 请求获取数据
    """
    week_start, week_end = get_current_week_range()
    week_label = get_week_number()

    print(f"\n[抓取] 正在抓取类目 [{CATEGORIES.get(category_id, '未知')}] (ID={category_id})...")

    if not os.path.exists(COOKIE_FILE):
        print(f"[错误] Cookie 文件不存在: {COOKIE_FILE}")
        print("   请先运行: python scripts/fastmoss_login_and_fetch.py")
        return []

    with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
        cookies = json.load(f)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[错误] 请先安装 Playwright: pip install playwright && playwright install chromium")
        return []

    all_products = []
    api_responses = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
            ]
        )
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            locale='zh-CN',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        )

        # 反检测
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh'] });
            window.chrome = { runtime: {} };
        """)

        context.add_cookies(cookies)
        page = context.new_page()

        # 拦截 API 响应
        captured_responses = []

        def handle_response(response):
            url = response.url
            if '/api/goods/saleRank' in url:
                try:
                    body = response.body()
                    data = json.loads(body)
                    captured_responses.append({
                        'url': url,
                        'data': data,
                    })
                    print(f"   [拦截] API 响应: {url.split('?')[0].split('/')[-1]} (status={response.status})")
                except Exception as e:
                    print(f"   [拦截] 解析失败: {e}")

        page.on('response', handle_response)

        # 先打开首页确保登录状态
        print("   打开 Fastmoss 首页...")
        page.goto('https://www.fastmoss.com/zh/dashboard', wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(3000)

        # 检查是否登录成功
        current_url = page.url
        print(f"   当前 URL: {current_url}")

        # 打开销量榜页面 - 日榜
        daily_url = f"https://www.fastmoss.com/zh/e-commerce/saleslist?region=PH&page=1&l1_cid={category_id}&date_type=1"
        print(f"   打开日榜页面...")
        page.goto(daily_url, wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(8000)

        # 打开销量榜页面 - 周榜
        weekly_url = f"https://www.fastmoss.com/zh/e-commerce/saleslist?region=PH&page=1&l1_cid={category_id}&date_type=2&date_value={week_label}"
        print(f"   打开周榜页面...")
        page.goto(weekly_url, wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(8000)

        browser.close()

    # 解析拦截到的 API 响应
    print(f"\n   拦截到 {len(captured_responses)} 个 API 响应")
    for resp_data in captured_responses:
        data = resp_data['data']
        if not isinstance(data, dict):
            continue

        code = data.get('code')
        if code != 200:
            print(f"   [跳过] API code={code}, msg={data.get('msg')}")
            continue

        data_field = data.get('data', {})
        if isinstance(data_field, dict):
            rank_list = data_field.get('rank_list', [])
            print(f"   [解析] rank_list: {len(rank_list)} items")
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
                }
                price = item.get('price', item.get('priceRange', ''))
                if isinstance(price, (int, float)):
                    product['price_min'] = float(price)
                    product['price_max'] = float(price)
                    product['price_range'] = f"₱{price}"
                elif isinstance(price, dict):
                    product['price_min'] = price.get('min', price.get('low', 0))
                    product['price_max'] = price.get('max', price.get('high', 0))
                    product['price_range'] = f"₱{product['price_min']} - ₱{product['price_max']}"
                all_products.append(product)
        elif isinstance(data_field, list):
            print(f"   [解析] data 是列表: {len(data_field)} items")
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
                    }
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
                f'fastmoss_playwright_{week_start}'
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
        f"- **数据来源**: Fastmoss 销量榜 (Playwright 拦截)",
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
        f"> 此报告由 `scripts/fetch_fastmoss_playwright.py` 自动生成",
        f"> 数据仅供参考，建议结合手动调研验证",
    ])

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"\n[报告] 行业趋势报告已生成: {report_path}")
    return report_path


def fetch_all_categories():
    results = {}
    for cid in ["1", "3", "8"]:
        products = fetch_saleslist_via_playwright(category_id=cid)
        if products:
            save_to_database(products, cid)
            results[cid] = len(products)
        else:
            print(f"   [警告] 类目 {cid} 未获取到数据")
    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Fastmoss Playwright 数据抓取工具')
    parser.add_argument('--category', default='8', help='类目ID (8=珠宝首饰, 1=女装, 3=美妆)')
    parser.add_argument('--all', action='store_true', help='抓取所有主要类目')
    parser.add_argument('--report-only', action='store_true', help='仅基于已有数据生成报告，不抓取')
    args = parser.parse_args()

    print(f"""
+===============================================+
|     Fastmoss Playwright 数据抓取工具           |
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
        products = fetch_saleslist_via_playwright(category_id=args.category)
        if products:
            save_to_database(products, args.category)
            generate_industry_report(args.category)
        else:
            print(f"\n[警告] 类目 {args.category} 未抓取到数据")
            print("   可能原因:")
            print("   1. Cookie 已过期 - 请重新登录 Fastmoss 并更新 Cookie")
            print("   2. 页面结构变更 - 请检查 debug HTML 文件")
            print("   3. 触发了反爬虫验证")


if __name__ == '__main__':
    main()
