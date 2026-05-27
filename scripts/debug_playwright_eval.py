"""
尝试在 Playwright 浏览器中执行 JS 来获取数据
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

    # 打开销量榜页面
    url = "https://www.fastmoss.com/zh/e-commerce/saleslist?region=PH&page=1&l1_cid=8&date_type=1"
    print(f"打开页面: {url}")
    page.goto(url, wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(15000)

    # 尝试通过 JS 获取数据
    print("\n尝试通过 JS 获取数据...")

    # 方法1: 检查 window.__NEXT_DATA__
    result1 = page.evaluate("""() => {
        try {
            return JSON.stringify(window.__NEXT_DATA__).substring(0, 500);
        } catch(e) {
            return 'Error: ' + e.message;
        }
    }""")
    print(f"__NEXT_DATA__: {result1[:200]}")

    # 方法2: 检查 window.__NEXT_F__
    result2 = page.evaluate("""() => {
        try {
            const f = window.__NEXT_F__;
            if (f) return 'Found, length=' + f.length;
            return 'Not found';
        } catch(e) {
            return 'Error: ' + e.message;
        }
    }""")
    print(f"__NEXT_F__: {result2}")

    # 方法3: 检查是否有全局变量存储了数据
    result3 = page.evaluate("""() => {
        const keys = Object.keys(window).filter(k => 
            k.includes('data') || k.includes('store') || k.includes('state') || 
            k.includes('cache') || k.includes('redux') || k.includes('__NEXT')
        );
        return JSON.stringify(keys);
    }""")
    print(f"相关全局变量: {result3}")

    # 方法4: 尝试直接 fetch API（在浏览器环境中）
    result4 = page.evaluate("""async () => {
        try {
            const resp = await fetch('/api/goods/saleRank?page=1&pagesize=10&order=1,2&region=PH&l1_cid=8&date_type=1');
            const data = await resp.json();
            return JSON.stringify(data).substring(0, 500);
        } catch(e) {
            return 'Error: ' + e.message;
        }
    }""")
    print(f"\n浏览器内 fetch API: {result4[:300]}")

    # 方法5: 检查页面中是否有数据表格
    result5 = page.evaluate("""() => {
        const tables = document.querySelectorAll('table');
        const results = [];
        tables.forEach((t, i) => {
            const rows = t.querySelectorAll('tbody tr');
            results.push(`Table ${i}: ${rows.length} rows`);
            if (rows.length > 0) {
                const cells = rows[0].querySelectorAll('td');
                results.push(`  First row: ${cells.length} cells`);
                cells.forEach((c, j) => {
                    results.push(`    Cell ${j}: ${c.innerText.substring(0, 50)}`);
                });
            }
        });
        return results.join('\\n');
    }""")
    print(f"\n页面表格数据:\n{result5}")

    # 方法6: 检查是否有 React 内部状态
    result6 = page.evaluate("""() => {
        const root = document.getElementById('__next');
        if (!root) return 'No __next root';
        const keys = Object.keys(root);
        const reactKeys = keys.filter(k => k.startsWith('__react'));
        return JSON.stringify(reactKeys);
    }""")
    print(f"\nReact 内部状态: {result6}")

    browser.close()
