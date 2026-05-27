"""
调试 Playwright 页面内容 - 检查 Fastmoss 页面实际渲染了什么
"""
import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, 'scripts')
COOKIE_FILE = os.path.join(SCRIPTS_DIR, 'fastmoss_cookies.json')

with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
    cookies = json.load(f)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-web-security',
        ]
    )
    context = browser.new_context(
        viewport={'width': 1280, 'height': 800},
        locale='zh-CN',
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    )
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh'] });
        window.chrome = { runtime: {} };
    """)
    context.add_cookies(cookies)
    page = context.new_page()

    # 拦截所有 API 请求
    api_log = []
    def handle_response(response):
        url = response.url
        if '/api/' in url:
            try:
                body = response.body()
                data = json.loads(body)
                api_log.append({
                    'url': url[:120],
                    'status': response.status,
                    'code': data.get('code', 'N/A') if isinstance(data, dict) else type(data).__name__,
                    'data_type': type(data.get('data', 'N/A')).__name__ if isinstance(data, dict) else type(data).__name__,
                })
            except:
                api_log.append({
                    'url': url[:120],
                    'status': response.status,
                    'code': 'parse_error',
                })

    page.on('response', handle_response)

    # 打开销量榜页面
    url = "https://www.fastmoss.com/zh/e-commerce/saleslist?region=PH&page=1&l1_cid=8&date_type=1"
    print(f"打开页面: {url}")
    page.goto(url, wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(15000)

    # 检查页面内容
    print(f"\n页面标题: {page.title()}")
    print(f"页面 URL: {page.url}")

    # 检查是否有表格数据
    tables = page.query_selector_all('table')
    print(f"\n表格数量: {len(tables)}")

    rows = page.query_selector_all('table tbody tr')
    print(f"表格行数: {len(rows)}")

    # 检查是否有商品卡片
    cards = page.query_selector_all('[class*="product"], [class*="card"], [class*="item"]')
    print(f"商品卡片: {len(cards)}")

    # 检查是否有数据表格
    data_tables = page.query_selector_all('[class*="table"], [class*="list"], [class*="rank"]')
    print(f"数据容器: {len(data_tables)}")

    # 获取页面文本
    body_text = page.inner_text('body')
    print(f"\n页面文本长度: {len(body_text)} 字符")
    print(f"页面文本前500字: {body_text[:500]}")

    # 检查是否有验证码
    if '验证' in body_text or '安全' in body_text:
        print("\n⚠️ 页面包含安全验证相关文字！")

    # 保存页面源码
    html = page.content()
    debug_path = os.path.join(SCRIPTS_DIR, 'fastmoss_debug_page.html')
    with open(debug_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"\n页面源码已保存: {debug_path}")

    # 打印所有 API 请求
    print(f"\n=== API 请求日志 ({len(api_log)} 个) ===")
    for log in api_log:
        print(f"  [{log['status']}] code={log['code']} data={log['data_type']} | {log['url']}")

    browser.close()
