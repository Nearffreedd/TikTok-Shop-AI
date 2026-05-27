"""
🔍 Fastmoss 竞品追踪专家 Agent
================================
功能：
  1. 登录 Fastmoss（首次手动，后续自动复用 Cookie）
  2. 抓取竞品店铺数据（商品列表、价格、销量、评分、视频）
  3. 与历史数据对比，输出增量分析报告
  4. 支持两种追踪模式：
     - A（对标分析）：我方已有产品，对比竞品做价格/销量对标
     - B（新品开发）：我方无产品，监控竞品挖掘选品机会
  5. 综合市场趋势分析（我方产品 + 多个竞品）

用法：
  python scripts/competitor_tracker.py --login              # 首次登录 Fastmoss
  python scripts/competitor_tracker.py --track "竞品名称"   # 追踪指定竞品
  python scripts/competitor_tracker.py --track-all           # 追踪所有竞品
  python scripts/competitor_tracker.py --report              # 生成竞品周报
  python scripts/competitor_tracker.py --market "产品名"     # 综合市场趋势分析
  python scripts/competitor_tracker.py --list                # 列出所有竞品
  python scripts/competitor_tracker.py --add                 # 添加新竞品（交互式）
  python scripts/competitor_tracker.py --history "竞品名称"  # 查看竞品历史数据
"""

import os
import sys
import json
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict
import dotenv

# ====== 路径配置 ======
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, 'scripts')
COMPETITORS_DIR = os.path.join(BASE_DIR, 'Layer1_Permanent', '03_Competitors')
WORKING_DIR = os.path.join(BASE_DIR, 'Layer2_Working')
COOKIE_FILE = os.path.join(SCRIPTS_DIR, 'fastmoss_cookies.json')
COMPETITOR_LIST_FILE = os.path.join(COMPETITORS_DIR, 'competitor_list.md')
PRODUCT_MAP_FILE = os.path.join(COMPETITORS_DIR, 'product_competitor_map.md')
DB_FILE = os.path.join(COMPETITORS_DIR, 'tracker_data.db')

# 确保目录存在
os.makedirs(COMPETITORS_DIR, exist_ok=True)
os.makedirs(WORKING_DIR, exist_ok=True)

# 加载 Fastmoss 账号配置
dotenv.load_dotenv(os.path.join(BASE_DIR, '.env.fastmoss'))

FASTMOSS_EMAIL = os.getenv('FASTMOSS_EMAIL', '')
FASTMOSS_PASSWORD = os.getenv('FASTMOSS_PASSWORD', '')

# ====== 数据模型 ======
@dataclass
class CompetitorProduct:
    """竞品商品数据"""
    product_id: str              # Fastmoss 商品ID
    title: str                   # 商品标题
    price: float = 0.0           # 当前价格
    sales_30d: int = 0           # 近30日销量
    rating: float = 0.0          # 评分
    video_count: int = 0         # 关联视频数
    top_video_views: int = 0     # 最高视频播放量
    top_video_likes: int = 0     # 最高视频点赞数
    top_video_comments: int = 0  # 最高视频评论数
    first_seen: str = ""         # 首次发现日期
    last_updated: str = ""       # 最后更新日期

@dataclass
class CompetitorShop:
    """竞品店铺数据"""
    shop_name: str               # 竞品名称
    shop_url: str                # Fastmoss 链接
    category: str = ""           # 主营类目
    track_mode: str = "A"        # 追踪模式 A/B
    total_products: int = 0      # 商品总数
    total_sales: int = 0         # 总销量
    shop_rating: float = 0.0     # 店铺评分
    products: List[CompetitorProduct] = field(default_factory=list)
    tracked_at: str = ""         # 追踪时间

# ====== 数据库操作 ======
def init_database():
    """初始化 SQLite 数据库"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # 竞品店铺表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS competitor_shops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_name TEXT NOT NULL,
            shop_url TEXT NOT NULL,
            category TEXT DEFAULT '',
            track_mode TEXT DEFAULT 'A',
            total_products INTEGER DEFAULT 0,
            total_sales INTEGER DEFAULT 0,
            shop_rating REAL DEFAULT 0.0,
            tracked_at TEXT NOT NULL,
            UNIQUE(shop_name, tracked_at)
        )
    ''')

    # 竞品商品表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS competitor_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_name TEXT NOT NULL,
            product_id TEXT NOT NULL,
            title TEXT DEFAULT '',
            price REAL DEFAULT 0.0,
            sales_30d INTEGER DEFAULT 0,
            rating REAL DEFAULT 0.0,
            video_count INTEGER DEFAULT 0,
            top_video_views INTEGER DEFAULT 0,
            top_video_likes INTEGER DEFAULT 0,
            top_video_comments INTEGER DEFAULT 0,
            tracked_at TEXT NOT NULL,
            UNIQUE(shop_name, product_id, tracked_at)
        )
    ''')

    conn.commit()
    conn.close()

def save_shop_data(shop: CompetitorShop):
    """保存店铺数据到数据库"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # 保存店铺概览
    cursor.execute('''
        INSERT OR REPLACE INTO competitor_shops
        (shop_name, shop_url, category, track_mode, total_products, total_sales, shop_rating, tracked_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (shop.shop_name, shop.shop_url, shop.category, shop.track_mode,
          shop.total_products, shop.total_sales, shop.shop_rating, shop.tracked_at))

    # 保存商品数据
    for product in shop.products:
        cursor.execute('''
            INSERT OR REPLACE INTO competitor_products
            (shop_name, product_id, title, price, sales_30d, rating,
             video_count, top_video_views, top_video_likes, top_video_comments, tracked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (shop.shop_name, product.product_id, product.title, product.price,
              product.sales_30d, product.rating, product.video_count,
              product.top_video_views, product.top_video_likes,
              product.top_video_comments, shop.tracked_at))

    conn.commit()
    conn.close()

def get_latest_shop_data(shop_name: str) -> Optional[CompetitorShop]:
    """获取竞品最近一次追踪数据"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # 获取最新追踪时间
    cursor.execute('''
        SELECT tracked_at FROM competitor_shops
        WHERE shop_name = ?
        ORDER BY tracked_at DESC LIMIT 1
    ''', (shop_name,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    latest_time = row[0]

    # 获取店铺概览
    cursor.execute('''
        SELECT shop_name, shop_url, category, track_mode,
               total_products, total_sales, shop_rating, tracked_at
        FROM competitor_shops
        WHERE shop_name = ? AND tracked_at = ?
    ''', (shop_name, latest_time))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    shop = CompetitorShop(
        shop_name=row[0], shop_url=row[1], category=row[2],
        track_mode=row[3], total_products=row[4], total_sales=row[5],
        shop_rating=row[6], tracked_at=row[7]
    )

    # 获取商品列表
    cursor.execute('''
        SELECT product_id, title, price, sales_30d, rating,
               video_count, top_video_views, top_video_likes, top_video_comments
        FROM competitor_products
        WHERE shop_name = ? AND tracked_at = ?
    ''', (shop_name, latest_time))

    for row in cursor.fetchall():
        product = CompetitorProduct(
            product_id=row[0], title=row[1], price=row[2],
            sales_30d=row[3], rating=row[4], video_count=row[5],
            top_video_views=row[6], top_video_likes=row[7],
            top_video_comments=row[8]
        )
        shop.products.append(product)

    conn.close()
    return shop

def get_shop_history(shop_name: str, days: int = 30) -> List[CompetitorShop]:
    """获取竞品历史追踪数据"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    cursor.execute('''
        SELECT DISTINCT tracked_at FROM competitor_shops
        WHERE shop_name = ? AND tracked_at >= ?
        ORDER BY tracked_at DESC
    ''', (shop_name, cutoff))

    history = []
    for (tracked_at,) in cursor.fetchall():
        cursor.execute('''
            SELECT shop_name, shop_url, category, track_mode,
                   total_products, total_sales, shop_rating, tracked_at
            FROM competitor_shops
            WHERE shop_name = ? AND tracked_at = ?
        ''', (shop_name, tracked_at))
        row = cursor.fetchone()
        if row:
            shop = CompetitorShop(
                shop_name=row[0], shop_url=row[1], category=row[2],
                track_mode=row[3], total_products=row[4], total_sales=row[5],
                shop_rating=row[6], tracked_at=row[7]
            )
            cursor.execute('''
                SELECT product_id, title, price, sales_30d, rating,
                       video_count, top_video_views, top_video_likes, top_video_comments
                FROM competitor_products
                WHERE shop_name = ? AND tracked_at = ?
            ''', (shop_name, tracked_at))
            for prod_row in cursor.fetchall():
                product = CompetitorProduct(
                    product_id=prod_row[0], title=prod_row[1], price=prod_row[2],
                    sales_30d=prod_row[3], rating=prod_row[4], video_count=prod_row[5],
                    top_video_views=prod_row[6], top_video_likes=prod_row[7],
                    top_video_comments=prod_row[8]
                )
                shop.products.append(product)
            history.append(shop)

    conn.close()
    return history

# ====== 竞品列表管理 ======
def load_competitor_list() -> List[Dict]:
    """从 competitor_list.md 加载竞品列表"""
    competitors = []

    if not os.path.exists(COMPETITOR_LIST_FILE):
        print(f"⚠️ 竞品列表文件不存在: {COMPETITOR_LIST_FILE}")
        return competitors

    with open(COMPETITOR_LIST_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    # 解析 Markdown 表格
    lines = content.split('\n')
    in_table = False
    for line in lines:
        if line.startswith('|') and '---' not in line:
            if in_table:
                cells = [c.strip() for c in line.split('|')[1:-1]]
                if len(cells) >= 7:
                    competitors.append({
                        'name': cells[1],
                        'url': cells[2],
                        'category': cells[3],
                        'track_mode': cells[4],
                        'added_date': cells[5],
                        'note': cells[6],
                    })
        elif line.startswith('|:---') or line.startswith('|---'):
            in_table = True

    return competitors

def load_product_competitor_map() -> List[Dict]:
    """从 product_competitor_map.md 加载产品-竞品对照表"""
    mappings = []

    if not os.path.exists(PRODUCT_MAP_FILE):
        print(f"⚠️ 产品-竞品对照表不存在: {PRODUCT_MAP_FILE}")
        return mappings

    with open(PRODUCT_MAP_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    in_table = False
    for line in lines:
        if line.startswith('|') and '---' not in line:
            if in_table:
                cells = [c.strip() for c in line.split('|')[1:-1]]
                if len(cells) >= 5:
                    mappings.append({
                        'product': cells[0],       # 我方产品
                        'product_url': cells[1],    # 产品链接
                        'competitor': cells[2],     # 对应竞品
                        'competitor_url': cells[3], # 竞品链接
                        'dimension': cells[4],      # 市场分析维度
                    })
        elif line.startswith('|:---') or line.startswith('|---'):
            in_table = True

    return mappings

# ====== Fastmoss 数据抓取（Playwright） ======
def login_fastmoss():
    """首次登录 Fastmoss，保存 Cookie"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ 请先安装 Playwright: pip install playwright && python -m playwright install chromium")
        return False

    print("🔐 正在打开 Fastmoss 登录页面...")
    print("   请在浏览器中手动完成登录（输入账号密码或扫码）")
    print("   登录成功后，回到此终端按 Enter 键保存 Cookie\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            locale='zh-CN'
        )
        page = context.new_page()

        # 访问 Fastmoss 登录页
        page.goto('https://www.fastmoss.com/zh/login')
        page.wait_for_timeout(3000)

        print("⏳ 请在浏览器中完成登录...")
        print("   登录成功后，回到此终端按 Enter 键继续...")
        input()

        # 等待一下确保 Cookie 已同步
        page.wait_for_timeout(1000)

        # 先访问首页确保 Cookie 完整
        try:
            page.goto('https://www.fastmoss.com/zh/', wait_until='networkidle', timeout=10000)
            page.wait_for_timeout(2000)
        except:
            pass

        # 保存 Cookie
        cookies = context.cookies()
        with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

        print(f"✅ Cookie 已保存到: {COOKIE_FILE}")
        print(f"   共保存 {len(cookies)} 个 Cookie")

        if len(cookies) == 0:
            print("⚠️ 警告: Cookie 为空，可能登录未成功")
            print("   请确认已在浏览器中完成登录后再按 Enter")

        browser.close()

    return True

def scrape_competitor_shop(shop_url: str, max_products: int = 50) -> CompetitorShop:
    """抓取竞品数据（支持商品详情页和店铺页）"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ 请先安装 Playwright")
        return None

    if not os.path.exists(COOKIE_FILE):
        print("❌ 未找到 Cookie 文件，请先运行 --login 登录")
        return None

    with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
        cookies = json.load(f)

    shop = CompetitorShop(
        shop_name="",
        shop_url=shop_url,
        tracked_at=datetime.now().strftime('%Y-%m-%d %H:%M')
    )

    with sync_playwright() as p:
        # 使用反检测参数绕过 Fastmoss 的 headless 检测
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

        # 加载 Cookie
        context.add_cookies(cookies)
        page = context.new_page()

        print(f"🌐 正在访问: {shop_url}")
        page.goto(shop_url, wait_until='networkidle')
        page.wait_for_timeout(5000)

        # 检查是否登录成功
        if 'login' in page.url.lower():
            print("⚠️ Cookie 已过期，请重新运行 --login")
            browser.close()
            return None

        # 判断是商品详情页还是店铺页
        is_product_page = '/e-commerce/detail/' in shop_url or '/product/' in shop_url

        if is_product_page:
            # ====== 商品详情页解析 ======
            print("📄 检测到商品详情页")
            
            # 获取页面完整文本
            body_text = page.inner_text('body')
            
            # 提取商品标题 (h1)
            try:
                title_el = page.query_selector('h1')
                product_title = title_el.inner_text().strip() if title_el else ""
            except:
                product_title = ""
            
            # 提取店铺名称 - 查找"店铺详情"旁边的店铺名
            shop_name = ""
            try:
                # 查找包含"店铺详情"的区域
                shop_section = page.query_selector('text=店铺详情')
                if shop_section:
                    parent = shop_section.evaluate('el => el.closest("div")?.nextElementSibling?.innerText || el.parentElement?.innerText')
                    if parent:
                        shop_name = parent.strip().split('\n')[0][:50]
            except:
                pass
            
            if not shop_name:
                # 尝试从页面文本中提取
                lines = body_text.split('\n')
                for i, line in enumerate(lines):
                    if '店铺详情' in line and i + 1 < len(lines):
                        shop_name = lines[i + 1].strip()[:50]
                        break
            
            shop.shop_name = shop_name or product_title[:30] or shop_url.split('/')[-1][:20]
            print(f"🏪 商品: {product_title[:60]}")
            print(f"🏪 店铺: {shop.shop_name}")
            
            # 提取价格
            price = 0.0
            price_match = re.search(r'价格[：:]\s*[₱$€¥]?\s*([\d,]+\.?\d*)', body_text)
            if price_match:
                price = float(price_match.group(1).replace(',', ''))
            
            # 提取总销量 - 注意 Fastmoss 页面中"总销量"后面跟的是 GMV 值
            # 实际销量在"人气指数"后面
            total_sales = 0
            # 先尝试从"人气指数"后面提取销量（格式：人气指数 4.08万 总销量 ₱xxx）
            sales_match = re.search(r'人气指数\s*([\d.]+)([万wW])?\s*总销量', body_text)
            if sales_match:
                val = float(sales_match.group(1).replace(',', ''))
                if sales_match.group(2):
                    total_sales = int(val * 10000)
                else:
                    total_sales = int(val)
            
            # 提取总GMV - "总销量"后面跟的是 GMV（格式：总销量 ₱1102.04万 总GMV）
            total_gmv = 0.0
            gmv_match = re.search(r'总销量\s*[₱$€¥]?\s*([\d.]+)([万wW])?\s*总GMV', body_text)
            if gmv_match:
                val = float(gmv_match.group(1).replace(',', ''))
                if gmv_match.group(2):
                    total_gmv = val * 10000
                else:
                    total_gmv = val
            
            # 提取评分
            rating = 0.0
            rating_match = re.search(r'(\d\.\d)\s*/\s*5', body_text)
            if rating_match:
                rating = float(rating_match.group(1))
            
            # 提取评论数
            comments = 0
            comments_match = re.search(r'评论数[：:]?\s*([\d,]+)', body_text)
            if comments_match:
                comments = int(comments_match.group(1).replace(',', ''))
            
            # 提取带货达人数
            creator_count = 0
            creator_match = re.search(r'带货达人数[：:]?\s*([\d,]+)', body_text)
            if creator_match:
                creator_count = int(creator_match.group(1).replace(',', ''))
            
            # 提取视频数量
            video_count = 0
            video_match = re.search(r'视频数量[：:]?\s*([\d,]+)', body_text)
            if video_match:
                video_count = int(video_match.group(1).replace(',', ''))
            
            # 提取佣金率
            commission = ""
            commission_match = re.search(r'佣金率[：:]?\s*([\d.]+%)', body_text)
            if commission_match:
                commission = commission_match.group(1)
            
            # 提取库存
            stock = ""
            stock_match = re.search(r'库存[：:]?\s*([\d万+]+)', body_text)
            if stock_match:
                stock = stock_match.group(1)
            
            # 提取上架日期
            listed_date = ""
            date_match = re.search(r'预估上架日期[：:]\s*([\d-]+)', body_text)
            if date_match:
                listed_date = date_match.group(1)
            
            # 提取商品热度指数
            heat_index = 0
            heat_match = re.search(r'商品热度指数[：:]?\s*([\d,]+)', body_text)
            if heat_match:
                heat_index = int(heat_match.group(1).replace(',', ''))
            
            # 提取人气指数
            popularity = 0
            pop_match = re.search(r'人气指数[：:]?\s*([\d,]+)', body_text)
            if pop_match:
                popularity = int(pop_match.group(1).replace(',', ''))
            
            # 提取菲律宾销量榜排名
            rank_ph = ""
            rank_match = re.search(r'菲律宾销量榜[：:]?\s*([\d,]+)', body_text)
            if rank_match:
                rank_ph = rank_match.group(1)
            
            # 提取类目
            category = ""
            cat_match = re.search(r'时尚配件\s*/\s*([^\n]+)', body_text)
            if cat_match:
                category = "时尚配件/" + cat_match.group(1).strip()
            
            # 设置店铺概览
            shop.total_products = 1  # 商品详情页只有1个商品
            shop.total_sales = total_sales
            shop.shop_rating = rating
            shop.category = category
            
            print(f"📊 价格: ₱{price:.2f}")
            print(f"📊 总销量: {total_sales:,}")
            print(f"📊 评分: {rating}/5 ({comments} 评论)")
            print(f"📊 带货达人: {creator_count} | 视频: {video_count}")
            print(f"📊 GMV: ₱{total_gmv:,.0f}")
            print(f"📊 佣金率: {commission} | 库存: {stock}")
            print(f"📊 上架: {listed_date} | 热度: {heat_index} | 人气: {popularity}")
            
            # 创建商品对象
            product = CompetitorProduct(
                product_id=shop_url.split('/')[-1][:30],
                title=product_title[:200] or "未知商品",
                price=price,
                sales_30d=total_sales,
                rating=rating,
                video_count=video_count,
                top_video_views=0,
                top_video_likes=0,
                top_video_comments=comments,
                first_seen=shop.tracked_at,
                last_updated=shop.tracked_at
            )
            shop.products.append(product)
            
            # 尝试点击"商品关联视频"Tab获取视频数据
            try:
                video_tab = page.query_selector('text=商品关联视频')
                if video_tab:
                    video_tab.click()
                    page.wait_for_timeout(3000)
                    
                    # 提取视频列表
                    video_elements = page.query_selector_all('[class*="video"], [class*="card"], [class*="item"]')
                    for el in video_elements[:5]:
                        text = el.inner_text().strip()
                        views_match = re.search(r'([\d.]+)([万wW])?\s*[播放次]', text)
                        likes_match = re.search(r'([\d.]+)([万wW])?\s*[点赞]', text)
                        
                        if views_match:
                            v = float(views_match.group(1).replace(',', ''))
                            if views_match.group(2):
                                v = v * 10000
                            if v > product.top_video_views:
                                product.top_video_views = int(v)
                        
                        if likes_match:
                            l = float(likes_match.group(1).replace(',', ''))
                            if likes_match.group(2):
                                l = l * 10000
                            if l > product.top_video_likes:
                                product.top_video_likes = int(l)
            except:
                pass
            
            print(f"✅ 商品数据提取完成")
            
        else:
            # ====== 店铺页解析（原有逻辑） ======
            print("📄 检测到店铺页")
            
            # 提取店铺名称
            try:
                shop_name_selectors = [
                    'h1', '.shop-name', '.store-name', '.seller-name',
                    '[class*="name"]', '[class*="title"] h1'
                ]
                for selector in shop_name_selectors:
                    el = page.query_selector(selector)
                    if el:
                        text = el.inner_text().strip()
                        if text and len(text) < 100:
                            shop.shop_name = text
                            break
                if not shop.shop_name:
                    shop.shop_name = shop_url.split('/')[-1][:20]
            except:
                shop.shop_name = shop_url.split('/')[-1][:20]

            print(f"🏪 店铺名称: {shop.shop_name}")

            # 提取店铺概览
            try:
                stats_selectors = [
                    '[class*="stat"]', '[class*="count"]', '[class*="overview"]',
                    '.el-statistic', '.stat-item', '.data-item'
                ]
                for selector in stats_selectors:
                    elements = page.query_selector_all(selector)
                    for el in elements:
                        text = el.inner_text().strip()
                        nums = re.findall(r'[\d,]+', text)
                        if nums:
                            val = int(nums[0].replace(',', ''))
                            if '商品' in text or '产品' in text:
                                shop.total_products = val
                            elif '销量' in text or '销售' in text:
                                shop.total_sales = val
                            elif '评分' in text or '分' in text:
                                shop.shop_rating = float(nums[0].replace(',', ''))
            except:
                pass

            print(f"📊 店铺概览: {shop.total_products} 商品, {shop.total_sales} 销量, {shop.shop_rating} 评分")

            # 提取商品列表
            print(f"📦 正在提取商品列表...")
            try:
                product_tabs = page.query_selector_all('a, button, [role="tab"], [class*="tab"]')
                for tab in product_tabs:
                    text = tab.inner_text().strip()
                    if '商品' in text or '产品' in text or 'Products' in text:
                        tab.click()
                        page.wait_for_timeout(2000)
                        break
            except:
                pass

            for i in range(3):
                page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                page.wait_for_timeout(1500)

            product_elements = page.query_selector_all('[class*="product"], [class*="card"], [class*="item"], tr, [class*="row"]')
            if len(product_elements) < 2:
                links = page.query_selector_all('a[href*="product"]')
                product_elements = links

            products_found = 0
            for el in product_elements:
                if products_found >= max_products:
                    break
                try:
                    text = el.inner_text().strip()
                    if not text or len(text) < 5:
                        continue
                    title = text.split('\n')[0][:100] if text else ""
                    prices = re.findall(r'[₱$€¥]?\s*[\d,]+\.?\d*', text)
                    price = 0.0
                    if prices:
                        price_str = prices[0].replace('₱', '').replace('$', '').replace('€', '').replace('¥', '').replace(',', '').strip()
                        try:
                            price = float(price_str)
                        except:
                            pass
                    sales = 0
                    sales_match = re.search(r'(\d[\d,]*)\s*[单件笔]', text)
                    if sales_match:
                        sales = int(sales_match.group(1).replace(',', ''))
                    rating = 0.0
                    rating_match = re.search(r'(\d\.?\d*)\s*[分星]', text)
                    if rating_match:
                        rating = float(rating_match.group(1))
                    product_id = ""
                    href = el.get_attribute('href') or ""
                    id_match = re.search(r'product[/=](\d+)', href)
                    if id_match:
                        product_id = id_match.group(1)
                    else:
                        product_id = f"unknown_{products_found}"
                    product = CompetitorProduct(
                        product_id=product_id, title=title[:200], price=price,
                        sales_30d=sales, rating=rating,
                        first_seen=shop.tracked_at, last_updated=shop.tracked_at
                    )
                    shop.products.append(product)
                    products_found += 1
                except Exception:
                    continue

            print(f"✅ 提取到 {len(shop.products)} 个商品")

        browser.close()

    return shop

# ====== 数据分析 ======
def compare_with_history(shop_name: str, current: CompetitorShop) -> Dict:
    """对比当前数据与历史数据，返回变化摘要"""
    previous = get_latest_shop_data(shop_name)

    changes = {
        'new_products': [],
        'price_changes': [],
        'sales_changes': [],
        'shop_changes': {},
        'is_first_track': previous is None
    }

    if not previous:
        return changes

    # 店铺级变化
    if current.total_products != previous.total_products:
        changes['shop_changes']['total_products'] = {
            'before': previous.total_products,
            'after': current.total_products,
            'diff': current.total_products - previous.total_products
        }

    if current.total_sales != previous.total_sales:
        changes['shop_changes']['total_sales'] = {
            'before': previous.total_sales,
            'after': current.total_sales,
            'diff': current.total_sales - previous.total_sales
        }

    # 商品级变化
    prev_product_ids = {p.product_id for p in previous.products}
    curr_product_ids = {p.product_id for p in current.products}

    # 新品
    new_ids = curr_product_ids - prev_product_ids
    changes['new_products'] = [p for p in current.products if p.product_id in new_ids]

    # 价格变化
    prev_price_map = {p.product_id: p.price for p in previous.products}
    for p in current.products:
        if p.product_id in prev_price_map and prev_price_map[p.product_id] > 0:
            old_price = prev_price_map[p.product_id]
            if abs(p.price - old_price) / old_price > 0.05:
                changes['price_changes'].append({
                    'product': p,
                    'old_price': old_price,
                    'new_price': p.price,
                    'change_pct': round((p.price - old_price) / old_price * 100, 1)
                })

    return changes

def generate_market_analysis(product_name: str) -> str:
    """综合市场趋势分析：我方产品 + 多个竞品"""
    mappings = load_product_competitor_map()

    related = [m for m in mappings if m['product'] == product_name]

    if not related:
        return f"⚠️ 未找到产品 '{product_name}' 的竞品对照信息，请先在 product_competitor_map.md 中添加"

    report = f"""# 市场趋势分析：{product_name}

> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}

## 参与分析的竞品

| 竞品 | 追踪模式 | 分析维度 |
|:---|:---:|:---|
"""
    for r in related:
        report += f"| {r['competitor']} | A | {r['dimension']} |\n"

    report += "\n## 各竞品最新数据\n\n"

    for r in related:
        shop = get_latest_shop_data(r['competitor'])
        if shop:
            report += f"""
### {r['competitor']}

| 指标 | 数值 |
|:---|:---|
| 商品总数 | {shop.total_products} |
| 总销量 | {shop.total_sales:,} |
| 店铺评分 | {shop.shop_rating} |
| 追踪时间 | {shop.tracked_at} |

**Top 5 商品：**
| 商品名 | 价格 | 近30日销量 | 评分 |
|:---|:---:|:---:|:---:|
"""
            for p in sorted(shop.products, key=lambda x: x.sales_30d, reverse=True)[:5]:
                report += f"| {p.title[:40]} | ₱{p.price:.2f} | {p.sales_30d:,} | {p.rating} |\n"

    report += "\n## 综合市场判断\n\n### 价格区间\n"
    all_prices = []
    for r in related:
        shop = get_latest_shop_data(r['competitor'])
        if shop:
            all_prices.extend([p.price for p in shop.products if p.price > 0])

    if all_prices:
        report += f"- 最低价：₱{min(all_prices):.2f}\n"
        report += f"- 最高价：₱{max(all_prices):.2f}\n"
        report += f"- 平均价：₱{sum(all_prices)/len(all_prices):.2f}\n"
        report += f"- 中位数：₱{sorted(all_prices)[len(all_prices)//2]:.2f}\n"

    report += f"""
### 竞争格局
- 参与分析的竞品数：{len(related)}
- 建议关注点：价格策略、新品动态、视频营销效果

### 行动建议
1. **价格策略**：根据市场价格区间调整我方定价
2. **新品监控**：关注竞品新品上架动态，快速跟进
3. **视频内容**：分析竞品高互动视频，优化我方内容策略

---
*报告由 🔍 Fastmoss 竞品追踪专家 Agent 自动生成*
"""

    return report

# ====== 报告生成 ======
def generate_track_report(shop: CompetitorShop, changes: Dict) -> str:
    """生成竞品追踪报告"""
    report = f"""# 竞品追踪报告：{shop.shop_name}

> 追踪时间：{shop.tracked_at}
> 数据来源：Fastmoss ({shop.shop_url})

## 店铺概览

| 指标 | 数值 |
|:---|:---|
| 商品总数 | {shop.total_products} |
| 总销量 | {shop.total_sales:,} |
| 店铺评分 | {shop.shop_rating} |
| 追踪模式 | {'A - 对标分析' if shop.track_mode == 'A' else 'B - 新品开发'} |

"""

    if not changes.get('is_first_track', True):
        report += """
## 与上次追踪对比

### 店铺级变化
| 指标 | 上次 | 本次 | 变化 |
|:---|:---:|:---:|:---:|
"""
        sc = changes.get('shop_changes', {})
        if 'total_products' in sc:
            c = sc['total_products']
            report += f"| 商品总数 | {c['before']} | {c['after']} | {'+' if c['diff'] > 0 else ''}{c['diff']} |\n"
        if 'total_sales' in sc:
            c = sc['total_sales']
            report += f"| 总销量 | {c['before']:,} | {c['after']:,} | {'+' if c['diff'] > 0 else ''}{c['diff']:,} |\n"

    # 新品
    if changes.get('new_products'):
        report += f"""
### 🆕 新品上架（{len(changes['new_products'])} 个）

| 商品名 | 价格 | 近30日销量 | 评分 |
|:---|:---:|:---:|:---:|
"""
        for p in changes['new_products'][:10]:
            report += f"| {p.title[:50]} | ₱{p.price:.2f} | {p.sales_30d:,} | {p.rating} |\n"

    # 价格变动
    if changes.get('price_changes'):
        report += f"""
### 💰 价格变动（{len(changes['price_changes'])} 个）

| 商品名 | 原价 | 现价 | 变动幅度 |
|:---|:---:|:---:|:---:|
"""
        for pc in changes['price_changes'][:10]:
            arrow = '📈' if pc['change_pct'] > 0 else '📉'
            report += f"| {pc['product'].title[:50]} | ₱{pc['old_price']:.2f} | ₱{pc['new_price']:.2f} | {arrow} {pc['change_pct']:+.1f}% |\n"

    # Top 商品
    report += """
## Top 10 热销商品

| 排名 | 商品名 | 价格 | 近30日销量 | 评分 |
|:---:|:---|:---:|:---:|:---:|
"""
    for i, p in enumerate(sorted(shop.products, key=lambda x: x.sales_30d, reverse=True)[:10], 1):
        report += f"| {i} | {p.title[:50]} | ₱{p.price:.2f} | {p.sales_30d:,} | {p.rating} |\n"

    # 视频数据
    top_video_products = [p for p in shop.products if p.top_video_views > 0]
    if top_video_products:
        report += """
## 📱 视频互动数据

| 商品名 | 最高播放量 | 最高点赞 | 最高评论 |
|:---|:---:|:---:|:---:|
"""
        for p in sorted(top_video_products, key=lambda x: x.top_video_views, reverse=True)[:5]:
            report += f"| {p.title[:50]} | {p.top_video_views:,} | {p.top_video_likes:,} | {p.top_video_comments:,} |\n"

    # 行动建议
    report += """
## 💡 行动建议

"""
    if changes.get('new_products'):
        report += f"- **新品关注**：竞品上架了 {len(changes['new_products'])} 个新品，建议分析其卖点和素材方向\n"
    if changes.get('price_changes'):
        price_drops = [pc for pc in changes['price_changes'] if pc['change_pct'] < 0]
        if price_drops:
            report += f"- **价格预警**：{len(price_drops)} 个商品降价，需关注是否影响我方定价策略\n"
    if shop.products:
        valid_prices = [p.price for p in shop.products if p.price > 0]
        if valid_prices:
            avg_price = sum(valid_prices) / len(valid_prices)
            report += f"- **价格参考**：竞品平均售价 ₱{avg_price:.2f}，可作为定价参考\n"

    report += """
---
*报告由 🔍 Fastmoss 竞品追踪专家 Agent 自动生成*
"""

    return report

def generate_weekly_report() -> str:
    """生成竞品周报"""
    competitors = load_competitor_list()

    report = """# 竞品周报

> 生成时间：""" + datetime.now().strftime('%Y-%m-%d %H:%M') + """
> 数据来源：Fastmoss

## 竞品动态摘要

| 竞品 | 商品数 | 总销量 | 评分 | 新品数 | 价格变动 |
|:---|:---:|:---:|:---:|:---:|:---:|
"""

    for comp in competitors:
        shop = get_latest_shop_data(comp['name'])
        if shop:
            history = get_shop_history(comp['name'], days=14)
            new_products_count = 0
            price_changes_count = 0

            if len(history) >= 2:
                prev = history[1] if len(history) > 1 else None
                if prev:
                    prev_ids = {p.product_id for p in prev.products}
                    curr_ids = {p.product_id for p in shop.products}
                    new_products_count = len(curr_ids - prev_ids)

                    prev_prices = {p.product_id: p.price for p in prev.products}
                    for p in shop.products:
                        if p.product_id in prev_prices and prev_prices[p.product_id] > 0:
                            if abs(p.price - prev_prices[p.product_id]) / prev_prices[p.product_id] > 0.05:
                                price_changes_count += 1

            report += f"| {comp['name']} | {shop.total_products} | {shop.total_sales:,} | {shop.shop_rating} | {new_products_count} | {price_changes_count} |\n"

    report += """
## 对我方的影响评估

"""
    for comp in competitors:
        shop = get_latest_shop_data(comp['name'])
        if shop and shop.products:
            valid_prices = [p.price for p in shop.products if p.price > 0]
            avg_price = sum(valid_prices) / len(valid_prices) if valid_prices else 0
            top_sales = sorted(shop.products, key=lambda x: x.sales_30d, reverse=True)[:3]
            report += f"""### {comp['name']}
- 平均售价：₱{avg_price:.2f}
- Top 3 热销品：{', '.join([p.title[:30] for p in top_sales])}
- 影响评估：待补充

"""

    report += """
## 应对建议

1. **价格策略**：根据竞品价格变动调整我方定价
2. **新品跟进**：关注竞品新品上架，快速响应
3. **内容优化**：参考竞品高互动视频优化我方素材

---
*报告由 🔍 Fastmoss 竞品追踪专家 Agent 自动生成*
"""

    return report


# ====== 主程序入口 ======
def print_header():
    """打印程序头部"""
    print("""
╔══════════════════════════════════════════════════╗
║     🔍 Fastmoss 竞品追踪专家 Agent 已启动        ║
║                                                  ║
║  用法：                                          ║
║  --login             首次登录 Fastmoss           ║
║  --track "竞品名称"   追踪指定竞品                ║
║  --track-all         追踪所有竞品                ║
║  --report            生成竞品周报                ║
║  --market "产品名"   综合市场趋势分析             ║
║  --list              列出所有竞品                ║
║  --add               添加新竞品（交互式）         ║
║  --history "竞品名称" 查看竞品历史数据            ║
╚══════════════════════════════════════════════════╝
""")

def cmd_login():
    """处理 --login 命令"""
    print_header()
    print("🔐 开始 Fastmoss 登录流程...\n")
    success = login_fastmoss()
    if success:
        print("\n✅ 登录成功！Cookie 已保存，后续追踪无需重复登录。")
        print("   现在可以运行 --track 或 --track-all 来追踪竞品了。")
    else:
        print("\n❌ 登录失败，请重试。")

def cmd_track(shop_name: str):
    """处理 --track 命令"""
    print_header()
    print(f"🎯 开始追踪竞品: {shop_name}\n")

    competitors = load_competitor_list()
    target = None
    for comp in competitors:
        if comp['name'] == shop_name:
            target = comp
            break

    if not target:
        print(f"❌ 未找到竞品 '{shop_name}'，请先在 competitor_list.md 中添加")
        print("   或使用 --add 命令添加")
        return

    print(f"📋 竞品信息:")
    print(f"   名称: {target['name']}")
    print(f"   链接: {target['url']}")
    print(f"   类目: {target['category']}")
    print(f"   模式: {'A - 对标分析' if target['track_mode'] == 'A' else 'B - 新品开发'}")
    print()

    # 初始化数据库
    init_database()

    # 抓取数据
    shop = scrape_competitor_shop(target['url'])
    if not shop:
        return

    # 补充竞品信息
    shop.shop_name = target['name']
    shop.category = target['category']
    shop.track_mode = target['track_mode']

    # 保存到数据库
    save_shop_data(shop)
    print(f"\n💾 数据已保存到数据库")

    # 对比历史数据
    changes = compare_with_history(target['name'], shop)

    # 生成报告
    report = generate_track_report(shop, changes)

    # 保存报告
    today = datetime.now().strftime('%Y%m%d')
    report_file = os.path.join(WORKING_DIR, f"竞品追踪_{target['name']}_{today}.md")
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n📄 追踪报告已生成: {report_file}")

    # 输出关键变化
    if changes.get('new_products'):
        print(f"\n🆕 发现 {len(changes['new_products'])} 个新品!")
        for p in changes['new_products'][:5]:
            print(f"   • {p.title[:50]} - ₱{p.price:.2f}")

    if changes.get('price_changes'):
        print(f"\n💰 {len(changes['price_changes'])} 个商品价格变动!")
        for pc in changes['price_changes'][:5]:
            print(f"   • {pc['product'].title[:40]}: ₱{pc['old_price']:.2f} → ₱{pc['new_price']:.2f} ({pc['change_pct']:+.1f}%)")

def cmd_track_all():
    """处理 --track-all 命令"""
    print_header()
    print("🎯 开始追踪所有竞品...\n")

    competitors = load_competitor_list()
    if not competitors:
        print("❌ 竞品列表为空，请先在 competitor_list.md 中添加竞品")
        return

    print(f"📋 共发现 {len(competitors)} 个竞品\n")

    for i, comp in enumerate(competitors, 1):
        print(f"{'='*50}")
        print(f"  [{i}/{len(competitors)}] 正在追踪: {comp['name']}")
        print(f"{'='*50}")
        cmd_track(comp['name'])
        print()

    print(f"{'='*50}")
    print(f"✅ 所有竞品追踪完成!")
    print(f"{'='*50}")

def cmd_report():
    """处理 --report 命令"""
    print_header()
    print("📊 生成竞品周报...\n")

    init_database()
    report = generate_weekly_report()

    today = datetime.now().strftime('%Y%m%d')
    report_file = os.path.join(WORKING_DIR, f"竞品周报_{today}.md")
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"📄 竞品周报已生成: {report_file}")

def cmd_market(product_name: str):
    """处理 --market 命令"""
    print_header()
    print(f"📈 综合市场趋势分析: {product_name}\n")

    report = generate_market_analysis(product_name)

    today = datetime.now().strftime('%Y%m%d')
    report_file = os.path.join(WORKING_DIR, f"市场趋势_{product_name}_{today}.md")
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"📄 市场趋势分析已生成: {report_file}")

def cmd_list():
    """处理 --list 命令"""
    print_header()
    print("📋 竞品列表\n")

    competitors = load_competitor_list()
    if not competitors:
        print("  暂无竞品，请先在 competitor_list.md 中添加")
        return

    print(f"{'名称':<20} {'类目':<15} {'模式':<8} {'添加日期':<12}")
    print("-" * 60)
    for comp in competitors:
        mode = "A-对标" if comp['track_mode'] == 'A' else "B-新品"
        print(f"{comp['name']:<20} {comp['category']:<15} {mode:<8} {comp['added_date']:<12}")

    print(f"\n共 {len(competitors)} 个竞品")

def cmd_add():
    """处理 --add 命令（交互式添加新竞品）"""
    print_header()
    print("➕ 添加新竞品\n")

    print("请提供以下信息（直接回车可跳过可选字段）：")
    name = input("竞品名称: ").strip()
    if not name:
        print("❌ 竞品名称不能为空")
        return

    url = input("Fastmoss 链接: ").strip()
    if not url:
        print("❌ Fastmoss 链接不能为空")
        return

    category = input("主营类目 (默认: 时尚配件): ").strip() or "时尚配件"

    mode_input = input("追踪模式 (A=对标分析/B=新品开发, 默认: A): ").strip().upper() or "A"
    track_mode = "A" if mode_input == "A" else "B"

    note = input("备注 (可选): ").strip() or ""

    today = datetime.now().strftime('%Y-%m-%d')

    # 追加到 competitor_list.md
    new_line = f"| {len(load_competitor_list()) + 1} | {name} | {url} | {category} | {track_mode} | {today} | {note} |\n"

    with open(COMPETITOR_LIST_FILE, 'a', encoding='utf-8') as f:
        f.write(new_line)

    print(f"\n✅ 竞品 '{name}' 已添加到列表")
    print(f"   链接: {url}")
    print(f"   模式: {'A - 对标分析' if track_mode == 'A' else 'B - 新品开发'}")
    print(f"\n现在可以运行 --track \"{name}\" 来追踪该竞品")

def cmd_history(shop_name: str):
    """处理 --history 命令"""
    print_header()
    print(f"📜 查看竞品历史数据: {shop_name}\n")

    history = get_shop_history(shop_name, days=90)

    if not history:
        print(f"❌ 未找到竞品 '{shop_name}' 的历史数据")
        return

    print(f"共 {len(history)} 次追踪记录\n")

    print(f"{'追踪时间':<20} {'商品数':<8} {'总销量':<12} {'评分':<8}")
    print("-" * 50)
    for h in history:
        print(f"{h.tracked_at:<20} {h.total_products:<8} {h.total_sales:<12,} {h.shop_rating:<8}")

    # 趋势分析
    if len(history) >= 2:
        print(f"\n📈 趋势分析（最近两次对比）:")
        latest = history[0]
        prev = history[1]

        prod_diff = latest.total_products - prev.total_products
        sales_diff = latest.total_sales - prev.total_sales

        print(f"   商品数: {prev.total_products} → {latest.total_products} ({'+' if prod_diff > 0 else ''}{prod_diff})")
        print(f"   总销量: {prev.total_sales:,} → {latest.total_sales:,} ({'+' if sales_diff > 0 else ''}{sales_diff:,})")


# ====== 主程序 ======
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_header()
        print("请指定操作命令，例如:")
        print("  python scripts/competitor_tracker.py --login")
        print("  python scripts/competitor_tracker.py --track \"竞品A\"")
        print("  python scripts/competitor_tracker.py --track-all")
        print("  python scripts/competitor_tracker.py --report")
        print("  python scripts/competitor_tracker.py --market \"SL07\"")
        print("  python scripts/competitor_tracker.py --list")
        print("  python scripts/competitor_tracker.py --add")
        print("  python scripts/competitor_tracker.py --history \"竞品A\"")
        sys.exit(1)

    command = sys.argv[1]

    if command == '--login':
        cmd_login()
    elif command == '--track':
        if len(sys.argv) < 3:
            print("❌ 请指定竞品名称，例如: --track \"竞品A\"")
            sys.exit(1)
        cmd_track(sys.argv[2])
    elif command == '--track-all':
        cmd_track_all()
    elif command == '--report':
        cmd_report()
    elif command == '--market':
        if len(sys.argv) < 3:
            print("❌ 请指定产品名称，例如: --market \"SL07\"")
            sys.exit(1)
        cmd_market(sys.argv[2])
    elif command == '--list':
        cmd_list()
    elif command == '--add':
        cmd_add()
    elif command == '--history':
        if len(sys.argv) < 3:
            print("❌ 请指定竞品名称，例如: --history \"竞品A\"")
            sys.exit(1)
        cmd_history(sys.argv[2])
    else:
        print(f"❌ 未知命令: {command}")
        print("可用命令: --login, --track, --track-all, --report, --market, --list, --add, --history")
        sys.exit(1)


