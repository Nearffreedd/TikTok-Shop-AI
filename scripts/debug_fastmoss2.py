"""
调试脚本2：在 headless 模式下查看页面文本内容
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
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            locale='zh-CN'
        )
        context.add_cookies(cookies)
        page = context.new_page()
        
        url = "https://www.fastmoss.com/zh/e-commerce/detail/1732701246104110537"
        page.goto(url, wait_until='networkidle')
        page.wait_for_timeout(5000)
        
        # 获取 body 文本
        body_text = page.inner_text('body')
        
        # 保存完整文本到文件
        with open(os.path.join(BASE_DIR, 'scripts', 'body_text.txt'), 'w', encoding='utf-8') as f:
            f.write(body_text)
        
        print(f"body_text 长度: {len(body_text)} 字符")
        
        # 搜索关键字段
        keywords = ['价格', '总销量', '总GMV', '评分', '评论数', '带货达人', '视频数量', 
                    '佣金率', '库存', '上架日期', '热度指数', '人气指数', '菲律宾', '店铺详情']
        
        print("\n=== 搜索关键字段 ===")
        for kw in keywords:
            idx = body_text.find(kw)
            if idx >= 0:
                print(f"  ✅ '{kw}' 找到，位置 {idx}")
                # 显示前后文
                start = max(0, idx - 20)
                end = min(len(body_text), idx + 60)
                print(f"     上下文: ...{body_text[start:end].replace(chr(10), ' ')}...")
            else:
                print(f"  ❌ '{kw}' 未找到")
        
        # 搜索价格模式
        print("\n=== 搜索价格模式 ===")
        price_patterns = [
            r'₱\s*[\d,]+\.?\d*',
            r'价格[：:]\s*[₱$€¥]?\s*[\d,]+\.?\d*',
            r'[\d,]+\.?\d*\s*万',
        ]
        for pat in price_patterns:
            matches = re.findall(pat, body_text)
            if matches:
                print(f"  ✅ 模式 '{pat}': {matches[:10]}")
            else:
                print(f"  ❌ 模式 '{pat}': 无匹配")
        
        # 查看页面标题
        print(f"\n=== 页面标题 ===")
        print(f"  title: {page.title()}")
        
        # 查看 h1
        try:
            h1 = page.query_selector('h1')
            if h1:
                print(f"  h1: {h1.inner_text().strip()[:100]}")
        except:
            pass
        
        # 查看所有 meta
        print(f"\n=== Meta 信息 ===")
        metas = page.query_selector_all('meta[name], meta[property]')
        for m in metas:
            name = m.get_attribute('name') or m.get_attribute('property') or ''
            content = m.get_attribute('content') or ''
            if content:
                print(f"  {name}: {content[:100]}")
        
        browser.close()

if __name__ == "__main__":
    debug()
