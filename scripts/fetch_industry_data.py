"""
Fastmoss 行业数据抓取脚本
============================
功能：从 Fastmoss 获取行业销量榜数据，存入数据库并存档报告

数据来源：
  - 销量榜：https://www.fastmoss.com/zh/e-commerce/saleslist?region=PH&l1_cid={类目ID}
  - 商品详情：https://www.fastmoss.com/zh/e-commerce/detail/{商品ID}

用法：
  python scripts/fetch_industry_data.py                      # 抓取默认类目（首饰）
  python scripts/fetch_industry_data.py --category 8          # 指定类目ID
  python scripts/fetch_industry_data.py --category 8 --week   # 指定周数
  python scripts/fetch_industry_data.py --all                 # 抓取多个类目
  python scripts/fetch_industry_data.py --report-only         # 仅基于已有数据生成报告
"""

import os
import sys
import json
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, 'scripts')
DB_PATH = os.path.join(BASE_DIR, 'Layer1_Permanent', '01_My_Shop', 'shop_data.db')
COOKIE_FILE = os.path.join(SCRIPTS_DIR, 'fastmoss_cookies.json')
INDUSTRY_DIR = os.path.join(BASE_DIR, 'Layer1_Permanent', '04_Industry')

# Fastmoss 类目映射（菲律宾站）
CATEGORIES = {
    "8": "珠宝首饰及配件",     # Jewelry & Accessories
    "1": "女装",
    "2": "男装",
    "3": "美妆个护",
    "4": "3C数码",
    "5": "家居生活",
    "6": "母婴用品",
    "7": "运动户外",
}

# 时间配置
DATE_TYPE_WEEKLY = "2"  # 周度数据

def ensure_db_tables():
    """确保行业数据表存在"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 行业销量榜数据（每周快照）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS industry_saleslist (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id TEXT NOT NULL,
            category_name TEXT,
            week_start TEXT NOT NULL,
            week_end TEXT NOT NULL,
            rank INTEGER,                              -- 排名
            product_name TEXT,                         -- 商品名称
            product_id TEXT,                           -- 商品ID
            shop_name TEXT,                            -- 店铺名称
            price_range TEXT,                          -- 价格区间
            total_sales TEXT,                          -- 总销量
            total_gmv TEXT,                            -- 总GMV
            source_file TEXT,                          -- 数据来源
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(category_id, week_start, week_end, rank)
        )
    ''')
    
    # 商品价格历史追踪
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS industry_price_history (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            product_name TEXT,
            price REAL,
            currency TEXT DEFAULT 'PHP',
            week_start TEXT NOT NULL,
            week_end TEXT NOT NULL,
            category_id TEXT,
            source TEXT DEFAULT 'fastmoss',
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(product_id, week_start, week_end)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("[OK] 行业数据表已就绪")


def get_current_week_range():
    """获取当前周的起止日期"""
    today = datetime.now()
    # 周一为一周开始
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday.strftime('%Y-%m-%d'), sunday.strftime('%Y-%m-%d')


def get_week_number():
    """获取当前周数 (YYYY-WW)"""
    today = datetime.now()
    iso = today.isocalendar()
    return f"{iso[0]}-{iso[1]:02d}"


def fetch_saleslist(category_id="8", headless=True):
    """
    使用 Playwright 抓取 Fastmoss 销量榜数据
    返回解析后的商品列表
    """
    week_start, week_end = get_current_week_range()
    week_label = get_week_number()
    url = f"https://www.fastmoss.com/zh/e-commerce/saleslist?region=PH&page=1&l1_cid={category_id}&date_type={DATE_TYPE_WEEKLY}&date_value={week_label}"
    
    print(f"\n[抓取] 正在抓取类目 [{CATEGORIES.get(category_id, '未知')}] (ID={category_id})...")
    print(f"   URL: {url}")
    
    if not os.path.exists(COOKIE_FILE):
        print(f"[错误] Cookie 文件不存在: {COOKIE_FILE}")
        print("   请先手动登录 Fastmoss 并导出 Cookie")
        return []
    
    with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
        cookies = json.load(f)
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[错误] 请先安装 Playwright: pip install playwright && playwright install chromium")
        return []
    
    products = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
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
            extra_http_headers={
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            }
        )
        
        # 注入反检测脚本
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh'] });
            window.chrome = { runtime: {} };
        """)
        
        context.add_cookies(cookies)
        page = context.new_page()
        
        print("   正在加载页面...")
        page.goto(url, wait_until='networkidle', timeout=60000)
        page.wait_for_timeout(5000)
        
        # 检查是否被拦截
        body_text = page.inner_text('body')
        if '验证' in body_text and '安全验证' in body_text:
            print("[警告] 触发了安全验证，尝试等待...")
            page.wait_for_timeout(10000)
            body_text = page.inner_text('body')
        
        print(f"   页面标题: {page.title()}")
        print(f"   页面内容长度: {len(body_text)} 字符")
        
        # 尝试多种解析策略
        
        # 策略1：查找表格行
        try:
            rows = page.query_selector_all('table tbody tr')
            if rows and len(rows) > 0:
                print(f"   [OK] 找到 {len(rows)} 行表格数据")
                for i, row in enumerate(rows[:50]):  # 最多取前50
                    cells = row.query_selector_all('td')
                    if cells and len(cells) >= 3:
                        row_data = [cell.inner_text().strip() for cell in cells]
                        products.append({
                            "rank": i + 1,
                            "raw_data": row_data,
                            "product_name": row_data[1] if len(row_data) > 1 else '',
                            "price": row_data[2] if len(row_data) > 2 else '',
                        })
        except Exception as e:
            print(f"   [警告] 表格解析失败: {e}")
        
        # 策略2：查找商品卡片
        if not products:
            try:
                cards = page.query_selector_all('[class*="card"], [class*="product"], [class*="item"]')
                print(f"   尝试卡片解析，找到 {len(cards)} 个卡片")
                for card in cards[:30]:
                    text = card.inner_text().strip()
                    if text and len(text) > 10:
                        products.append({
                            "rank": len(products) + 1,
                            "text": text[:200],
                        })
            except Exception as e:
                print(f"   [警告] 卡片解析失败: {e}")
        
        # 保存页面源码用于调试
        debug_path = os.path.join(SCRIPTS_DIR, f'fastmoss_debug_{category_id}.html')
        try:
            html = page.content()
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"   [保存] 页面源码已保存: {debug_path}")
        except:
            pass
        
        browser.close()
    
    print(f"   [结果] 解析到 {len(products)} 个商品数据")
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
        product_name = product.get('product_name', product.get('text', f'商品_{rank}'))[:200]
        product_id = product.get('product_id', f'fastmoss_{category_id}_{rank}')
        shop_name = product.get('shop_name', '')
        price_range = product.get('price', product.get('price_range', ''))
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO industry_saleslist
                (category_id, category_name, week_start, week_end, rank,
                 product_name, product_id, shop_name, price_range,
                 total_sales, total_gmv, source_file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                category_id, category_name, week_start, week_end, rank,
                product_name, product_id, shop_name, price_range,
                product.get('total_sales', ''), product.get('total_gmv', ''),
                f'fastmoss_weekly_{week_start}'
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
    
    # 读取本周数据
    cursor.execute('''
        SELECT rank, product_name, shop_name, price_range, total_sales, total_gmv
        FROM industry_saleslist
        WHERE category_id = ? AND week_start = ?
        ORDER BY rank
        LIMIT 30
    ''', (category_id, week_start))
    weekly_data = cursor.fetchall()
    
    # 读取历史价格数据
    cursor.execute('''
        SELECT product_name, price, week_start
        FROM industry_price_history
        WHERE category_id = ?
        ORDER BY week_start DESC, product_name
        LIMIT 50
    ''', (category_id,))
    price_history = cursor.fetchall()
    
    conn.close()
    
    # 生成报告
    today = datetime.now().strftime('%Y%m%d')
    report_path = os.path.join(INDUSTRY_DIR, f'行业趋势周报_{category_name}_{today}.md')
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    
    # 构建报告内容
    lines = [
        f"# 行业趋势周报：{category_name}",
        f"",
        f"- **抓取时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- **数据周期**: {week_start} ~ {week_end}",
        f"- **数据来源**: Fastmoss 销量榜",
        f"",
        f"## Top 30 热销商品",
        f"",
        f"| 排名 | 商品名称 | 店铺 | 价格区间 | 总销量 | 总GMV |",
        f"|:---:|:---|:---|:---|:---:|:---:|",
    ]
    
    for row in weekly_data:
        rank, name, shop, price, sales, gmv = row
        name_display = (name or '未知')[:30]
        shop_display = (shop or '未知')[:20]
        lines.append(f"| {rank} | {name_display} | {shop_display} | {price or '-'} | {sales or '-'} | {gmv or '-'} |")
    
    if not weekly_data:
        lines.append(f"| — | 暂无数据 | — | — | — | — |")
    
    # 价格趋势
    if price_history:
        lines.extend([
            f"",
            f"## 价格趋势（历史对比）",
            f"",
            f"| 商品 | 价格 | 周 |",
            f"|:---|:---:|:---:|",
        ])
        for row in price_history[:20]:
            name, price, week = row
            lines.append(f"| {(name or '未知')[:30]} | {price or '-'} | {week} |")
    
    lines.extend([
        f"",
        f"---",
        f"",
        f"## 分析摘要",
        f"",
        f"> 此报告由 `scripts/fetch_industry_data.py` 自动生成",
        f"> 数据仅供参考，建议结合手动调研验证",
    ])
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"\n[报告] 行业趋势报告已生成: {report_path}")
    return report_path


def fetch_all_categories():
    """抓取所有主要类目的数据"""
    results = {}
    for cid in ["1", "3", "8"]:  # 重点关注女装、美妆、首饰
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
    parser.add_argument('--headless', action='store_true', default=True, help='无头模式')
    parser.add_argument('--all', action='store_true', help='抓取所有主要类目')
    parser.add_argument('--report-only', action='store_true', help='仅基于已有数据生成报告，不抓取')
    args = parser.parse_args()
    
    print(f"""
+===============================================+
|     Fastmoss 行业数据抓取工具                  |
|                                                 |
|     数据源: https://www.fastmoss.com           |
|     数据库: {os.path.basename(DB_PATH)}
+===============================================+
""")
    
    # 确保数据库表存在
    ensure_db_tables()
    
    if args.report_only:
        # 仅生成报告
        generate_industry_report(args.category)
        return
    
    if args.all:
        # 抓取所有主要类目
        results = fetch_all_categories()
        print(f"\n{'='*50}")
        print("  抓取完成!")
        for cid, count in results.items():
            print(f"  - {CATEGORIES.get(cid, cid)}: {count} 条")
        # 生成本周报告
        for cid in results:
            generate_industry_report(cid)
    else:
        # 抓取指定类目
        products = fetch_saleslist(category_id=args.category, headless=args.headless)
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
