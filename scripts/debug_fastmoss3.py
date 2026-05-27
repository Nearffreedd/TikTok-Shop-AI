"""
调试脚本3：测试反检测参数能否绕过 Fastmoss 的拦截
"""
import json
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COOKIE_FILE = os.path.join(BASE_DIR, 'scripts', 'fastmoss_cookies.json')

def debug():
    from playwright.sync_api import sync_playwright
    
    with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
        cookies = json.load(f)
    
    with sync_playwright() as p:
        # 使用反检测参数
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
        
        context.add_cookies(cookies)
        page = context.new_page()
        
        url = "https://www.fastmoss.com/zh/e-commerce/detail/1732701246104110537"
        print(f"正在访问: {url}")
        page.goto(url, wait_until='networkidle')
        page.wait_for_timeout(5000)
        
        print(f"页面标题: {page.title()}")
        
        body_text = page.inner_text('body')
        print(f"body_text 长度: {len(body_text)} 字符")
        
        # 搜索关键字段
        keywords = ['价格', '总销量', '总GMV', '评分', '评论数', '带货达人', '视频数量', 
                    '佣金率', '库存', '上架日期', '热度指数', '人气指数', '菲律宾', '店铺详情']
        
        print("\n=== 搜索关键字段 ===")
        for kw in keywords:
            idx = body_text.find(kw)
            if idx >= 0:
                start = max(0, idx - 20)
                end = min(len(body_text), idx + 60)
                print(f"  ✅ '{kw}': ...{body_text[start:end].replace(chr(10), ' ')}...")
            else:
                print(f"  ❌ '{kw}' 未找到")
        
        # 搜索价格
        print("\n=== 搜索价格 ===")
        price_matches = re.findall(r'₱\s*[\d,]+\.?\d*', body_text)
        print(f"  ₱ 价格: {price_matches[:10]}")
        
        # 搜索数字+万
        wan_matches = re.findall(r'[\d.]+万', body_text)
        print(f"  万: {wan_matches[:10]}")
        
        browser.close()

if __name__ == "__main__":
    debug()
