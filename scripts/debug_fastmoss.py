"""
调试脚本：查看 Fastmoss 店铺页面的实际 HTML 结构
"""
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COOKIE_FILE = os.path.join(BASE_DIR, 'scripts', 'fastmoss_cookies.json')

def debug_page():
    from playwright.sync_api import sync_playwright
    
    with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
        cookies = json.load(f)
    
    print(f"已加载 {len(cookies)} 个 Cookie")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # 有头模式方便观察
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            locale='zh-CN'
        )
        context.add_cookies(cookies)
        page = context.new_page()
        
        url = "https://www.fastmoss.com/zh/e-commerce/detail/1732701246104110537"
        print(f"正在访问: {url}")
        page.goto(url, wait_until='networkidle')
        page.wait_for_timeout(5000)
        
        print(f"当前URL: {page.url}")
        print(f"页面标题: {page.title()}")
        
        # 保存页面截图
        page.screenshot(path=os.path.join(BASE_DIR, 'scripts', 'fastmoss_debug.png'))
        print("截图已保存: scripts/fastmoss_debug.png")
        
        # 获取页面主要文本内容
        body_text = page.inner_text('body')
        print(f"\n=== 页面文本内容 (前2000字符) ===")
        print(body_text[:2000])
        
        # 获取所有 h1-h3 标题
        print(f"\n=== 页面标题 ===")
        for tag in ['h1', 'h2', 'h3']:
            elements = page.query_selector_all(tag)
            for el in elements:
                print(f"  {tag}: {el.inner_text().strip()[:100]}")
        
        # 获取所有链接
        print(f"\n=== 所有链接 (前30个) ===")
        links = page.query_selector_all('a')
        for i, link in enumerate(links[:30]):
            href = link.get_attribute('href') or ''
            text = link.inner_text().strip()[:60]
            if text or href:
                print(f"  [{i}] {text} -> {href}")
        
        # 获取所有有 class 的 div
        print(f"\n=== 主要 div 结构 ===")
        divs = page.query_selector_all('div[class]')
        for div in divs[:40]:
            cls = div.get_attribute('class') or ''
            text = div.inner_text().strip()[:80]
            if text:
                print(f"  class='{cls[:60]}' -> {text}")
        
        # 查找包含数字/价格/销量的元素
        print(f"\n=== 包含数字的元素 ===")
        import re
        all_elements = page.query_selector_all('*')
        for el in all_elements:
            try:
                text = el.inner_text().strip()
                if re.search(r'[\d,]+', text) and len(text) < 200:
                    tag = el.evaluate('el => el.tagName.toLowerCase()')
                    cls = (el.get_attribute('class') or '')[:40]
                    print(f"  <{tag}> class='{cls}' -> {text[:150]}")
            except:
                pass
        
        input("\n按 Enter 关闭浏览器...")
        browser.close()

if __name__ == "__main__":
    debug_page()
