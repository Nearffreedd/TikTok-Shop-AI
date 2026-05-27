"""
数据库初始化脚本
- 创建 shop_data.db
- 建立商品款式表（style_catalog）
- 建立店铺表（shops）
- 建立商品周数据表（product_weekly）
- 导入已有历史数据
"""

import sqlite3
import os
import sys

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                       'Layer1_Permanent', '01_My_Shop', 'shop_data.db')

def init_database():
    """初始化数据库，创建所有表"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # ========== 1. 店铺表 ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shops (
            shop_id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_name TEXT NOT NULL UNIQUE,        -- 店铺名称，如 Picknbuy
            shop_code TEXT NOT NULL UNIQUE,         -- 店铺代码，如 PNB
            platform TEXT DEFAULT 'TikTok Shop',    -- 平台
            market TEXT DEFAULT '菲律宾',            -- 目标市场
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # ========== 2. 商品款式表 ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS style_catalog (
            style_id INTEGER PRIMARY KEY AUTOINCREMENT,
            style_code TEXT NOT NULL UNIQUE,         -- 款式代码，如 ST01, SL06
            style_name TEXT NOT NULL,                -- 款式名称，如 Clover Set
            category TEXT,                           -- 类目，如 手链/项链/眼镜
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # ========== 3. 商品表（每个店铺的每个链接） ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_id INTEGER NOT NULL,                -- 所属店铺
            platform_product_id TEXT NOT NULL,        -- 平台商品ID（TikTok的ID）
            product_name TEXT NOT NULL,               -- 商品名称
            style_id INTEGER,                        -- 关联款式ID（可为空，后续补充）
            status TEXT DEFAULT 'Active',             -- 当前状态 Active/Inactive
            first_seen_date TEXT,                     -- 首次出现日期
            last_seen_date TEXT,                      -- 最后出现日期
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (shop_id) REFERENCES shops(shop_id),
            FOREIGN KEY (style_id) REFERENCES style_catalog(style_id),
            UNIQUE(shop_id, platform_product_id)
        )
    ''')
    
    # ========== 4. 商品周数据表（核心数据） ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS product_weekly (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,             -- 关联商品ID
            week_start TEXT NOT NULL,                 -- 周开始日期 (YYYY-MM-DD)
            week_end TEXT NOT NULL,                   -- 周结束日期 (YYYY-MM-DD)
            
            -- 整体表现
            gmv REAL DEFAULT 0,                       -- GMV (PHP)
            units_sold INTEGER DEFAULT 0,             -- 成交件数
            orders INTEGER DEFAULT 0,                 -- 订单数
            refund_units REAL DEFAULT 0,              -- 已退款商品件数
            
            -- 商城渠道
            shop_gmv REAL DEFAULT 0,
            shop_units INTEGER DEFAULT 0,
            shop_impressions INTEGER DEFAULT 0,
            shop_page_views INTEGER DEFAULT 0,
            shop_unique_visitors INTEGER DEFAULT 0,
            shop_click_rate REAL DEFAULT 0,
            shop_conversion_rate REAL DEFAULT 0,
            
            -- 视频渠道
            video_gmv REAL DEFAULT 0,
            video_units INTEGER DEFAULT 0,
            video_impressions INTEGER DEFAULT 0,
            video_page_views INTEGER DEFAULT 0,
            video_unique_visitors INTEGER DEFAULT 0,
            video_click_rate REAL DEFAULT 0,
            video_conversion_rate REAL DEFAULT 0,
            
            -- 直播渠道
            live_gmv REAL DEFAULT 0,
            live_units INTEGER DEFAULT 0,
            live_impressions INTEGER DEFAULT 0,
            live_page_views INTEGER DEFAULT 0,
            live_unique_visitors INTEGER DEFAULT 0,
            live_click_rate REAL DEFAULT 0,
            live_conversion_rate REAL DEFAULT 0,
            
            -- 商品卡渠道
            card_gmv REAL DEFAULT 0,
            card_units INTEGER DEFAULT 0,
            card_impressions INTEGER DEFAULT 0,
            card_page_views INTEGER DEFAULT 0,
            card_unique_visitors INTEGER DEFAULT 0,
            card_click_rate REAL DEFAULT 0,
            card_conversion_rate REAL DEFAULT 0,
            
            -- 元数据
            source_file TEXT,                         -- 数据来源文件名
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (product_id) REFERENCES products(product_id),
            UNIQUE(product_id, week_start, week_end)
        )
    ''')
    
    # ========== 5. 视频创意主表 ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS video_creatives (
            video_id TEXT PRIMARY KEY,              -- TikTok 视频 ID
            video_title TEXT,                        -- 视频标题/文案
            username TEXT,                           -- 达人用户名
            publish_date TEXT,                       -- 发布时间
            video_source TEXT,                       -- 来源（上传/...）
            first_seen_week TEXT,                    -- 首次出现周
            last_seen_week TEXT,                     -- 最后出现周
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # ========== 6. 视频↔商品关联表 ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS video_product_link (
            link_id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT NOT NULL,                  -- FK → video_creatives
            platform_product_id TEXT NOT NULL,        -- FK → products.platform_product_id（可为 "0"）
            authorization_type TEXT,                  -- 授权类型
            authorization_status TEXT,                -- 授权状态
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(video_id, platform_product_id)
        )
    ''')
    
    # ========== 7. 视频周表现表 ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS video_weekly_perf (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT NOT NULL,                  -- FK → video_creatives
            week_start TEXT NOT NULL,                 -- 周开始
            week_end TEXT NOT NULL,                   -- 周结束
            platform_product_id TEXT,                 -- 该条数据关联的商品 ID
            revenue REAL DEFAULT 0,                   -- 总收入 (USD)
            sku_orders INTEGER DEFAULT 0,             -- SKU 订单数
            cost REAL DEFAULT 0,                      -- 成本/花费 (USD)
            avg_order_cost REAL DEFAULT 0,            -- 平均下单成本
            roi REAL DEFAULT 0,                       -- ROI
            ad_impressions INTEGER DEFAULT 0,         -- 广告曝光
            ad_clicks INTEGER DEFAULT 0,              -- 广告点击
            ad_ctr REAL DEFAULT 0,                    -- 广告点击率
            ad_conversion_rate REAL DEFAULT 0,        -- 广告转化率
            play_2s_rate REAL DEFAULT 0,              -- 2秒播放率
            play_6s_rate REAL DEFAULT 0,              -- 6秒播放率
            tag_label TEXT,                           -- 标签（成效出色等）
            source_file TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(video_id, week_start, week_end, platform_product_id)
        )
    ''')
    
    # ========== 8. GMV MAX 广告投放周数据表 ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gmvmax_campaign_weekly (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id TEXT NOT NULL,           -- TikTok 广告计划 ID
            campaign_name TEXT NOT NULL,          -- 广告计划名称
            week_start TEXT NOT NULL,             -- 周开始 (YYYY-MM-DD)
            week_end TEXT NOT NULL,               -- 周结束 (YYYY-MM-DD)
            product_code TEXT,                    -- 解析出的产品代码 (ST01/SL06等)
            product_code2 TEXT,                   -- 联投时的第二个代码
            target_roi REAL,                      -- 从名称解析的目标 ROI
            extracted_budget REAL,                -- 从名称解析的预算
            cost REAL DEFAULT 0,                  -- 成本 (USD)
            net_cost REAL DEFAULT 0,              -- 净成本 (USD)
            current_budget REAL DEFAULT 0,        -- 当前预算 (USD)
            sku_orders INTEGER DEFAULT 0,         -- SKU 订单数
            avg_order_cost REAL DEFAULT 0,        -- 平均下单成本
            total_revenue REAL DEFAULT 0,         -- 总收入 (USD)
            roi REAL DEFAULT 0,                   -- 实际 ROI
            currency TEXT DEFAULT 'USD',
            roi_protection TEXT,                   -- ROI 保护状态
            optimization_mode TEXT,                -- 优化模式
            source_file TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(campaign_id, week_start, week_end)
        )
    ''')
    
    # ========== 9. 联盟周数据表 ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS affiliate_weekly (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            week_start TEXT NOT NULL,
            week_end TEXT NOT NULL,
            affiliate_gmv REAL DEFAULT 0,
            affiliate_units INTEGER DEFAULT 0,
            estimated_commission REAL DEFAULT 0,
            sample_count INTEGER DEFAULT 0,
            selling_creators INTEGER DEFAULT 0,
            live_count INTEGER DEFAULT 0,
            video_count INTEGER DEFAULT 0,
            refunded_gmv REAL DEFAULT 0,
            refunded_units INTEGER DEFAULT 0,
            fixed_fee REAL DEFAULT 0,
            source_file TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(product_id),
            UNIQUE(product_id, week_start, week_end)
        )
    ''')
    
    # ========== 10. 创建索引 ==========
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_product_weekly_product ON product_weekly(product_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_product_weekly_week ON product_weekly(week_start, week_end)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_shop ON products(shop_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_style ON products(style_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_video_link_video ON video_product_link(video_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_video_link_product ON video_product_link(platform_product_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_video_perf_video ON video_weekly_perf(video_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_video_perf_week ON video_weekly_perf(week_start, week_end)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_video_perf_product ON video_weekly_perf(platform_product_id)')
    
    # ========== 11. 行业销量榜数据表（每周快照） ==========
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
    
    # ========== 12. 商品价格历史追踪表 ==========
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
    
    print(f'[OK] 数据库初始化完成: {DB_PATH}')
    print(f'     表: shops, style_catalog, products, product_weekly')
    print(f'     表: video_creatives, video_product_link, video_weekly_perf')
    print(f'     表: gmvmax_campaign_weekly, affiliate_weekly')
    print(f'     表: industry_saleslist, industry_price_history')


def seed_initial_data():
    """导入初始数据：店铺、款式、已有Excel数据"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # ===== 1. 插入店铺 =====
    shops = [
        ('Picknbuy', 'PNB', 'TikTok Shop', '菲律宾'),
    ]
    for shop in shops:
        cursor.execute('''
            INSERT OR IGNORE INTO shops (shop_name, shop_code, platform, market)
            VALUES (?, ?, ?, ?)
        ''', shop)
    
    # ===== 2. 插入款式 =====
    styles = [
        ('ST01', 'Clover Set', '首饰套装'),
        ('SL06', 'Bible Bracelet', '手链'),
        ('SL07', 'Citrine Bracelet', '手链'),
        ('MJ01', 'Sunglasses', '太阳镜'),
        ('FQ01', 'Cherry Hair Tie and Bracelet', '发饰/手链'),
    ]
    for style in styles:
        cursor.execute('''
            INSERT OR IGNORE INTO style_catalog (style_code, style_name, category)
            VALUES (?, ?, ?)
        ''', style)
    
    conn.commit()
    conn.close()
    print('[OK] 初始数据导入完成（店铺 + 款式）')

if __name__ == '__main__':
    init_database()
    seed_initial_data()
