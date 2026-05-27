"""
Fastmoss 自动登录 + 数据抓取工具
===================================
使用 Playwright 自动登录 Fastmoss（手机号+密码方式），
获取带登录凭证的 Cookie，然后抓取行业数据并生成报告。

登录流程：
  1. 打开 https://www.fastmoss.com/zh/dashboard
  2. 自动填写手机号和密码
  3. 点击登录按钮
  4. 出现滑块验证码 → 等待用户手动拖动完成
  5. 登录成功后自动保存 Cookie 并抓取数据

用法：
  直接运行（自动从 .env.fastmoss 读取账号密码）:
    python scripts/fastmoss_login_and_fetch.py
"""

import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fix_encoding

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, 'scripts')
COOKIE_FILE = os.path.join(SCRIPTS_DIR, 'fastmoss_cookies.json')

# ====== 配置区域 ======
REGION = "PH"
L1_CID = 8
DATE_TYPE = 1
# =====================


def load_env_account():
    """从 .env.fastmoss 文件读取账号密码（手机号+密码）"""
    env_path = os.path.join(BASE_DIR, '.env.fastmoss')
    phone, password = None, None
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('FASTMOSS_EMAIL='):
                    phone = line.split('=', 1)[1].strip().strip('"').strip("'")
                elif line.startswith('FASTMOSS_PASSWORD='):
                    password = line.split('=', 1)[1].strip().strip('"').strip("'")
    if phone and password:
        return phone, password

    # 回退到 .env
    env_path = os.path.join(BASE_DIR, '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('FASTMOSS_EMAIL='):
                    phone = line.split('=', 1)[1].strip().strip('"').strip("'")
                elif line.startswith('FASTMOSS_PASSWORD='):
                    password = line.split('=', 1)[1].strip().strip('"').strip("'")
    return phone, password


def login_and_get_cookies(phone, password):
    """使用 Playwright 自动登录 Fastmoss，返回带登录凭证的 cookies"""
    from playwright.sync_api import sync_playwright

    print(f'🔑 正在登录 Fastmoss...')
    print(f'   手机号: {phone}')

    cookies = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
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

        # 反检测
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh'] });
            window.chrome = { runtime: {} };
        """)

        page = context.new_page()

        # 打开登录页面（dashboard 页面会跳转到登录页）
        print('   打开 Fastmoss...')
        page.goto('https://www.fastmoss.com/zh/dashboard', wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(3000)

        # 截图保存初始状态
        page.screenshot(path=os.path.join(SCRIPTS_DIR, 'fastmoss_login_page.png'))
        print('   📸 初始页面截图已保存')

        # 检查当前 URL，判断是否在登录页面
        current_url = page.url
        print(f'   当前 URL: {current_url}')

        # 尝试填写登录表单
        try:
            # 等待输入框出现
            page.wait_for_selector('input', timeout=15000)
            print('   ✅ 找到输入框')

            # 获取所有可见的输入框
            inputs = page.query_selector_all('input:visible')
            print(f'   发现 {len(inputs)} 个可见输入框')

            # 填写第一个输入框（手机号）
            if len(inputs) >= 1:
                inputs[0].fill(phone)
                print('   ✅ 已填写手机号')

            # 填写第二个输入框（密码）
            if len(inputs) >= 2:
                inputs[1].fill(password)
                print('   ✅ 已填写密码')

            # 点击登录按钮
            login_btn = page.query_selector('button[type="submit"]')
            if not login_btn:
                login_btn = page.query_selector('button:has-text("登录")')
            if not login_btn:
                login_btn = page.query_selector('button:has-text("Sign")')
            if not login_btn:
                login_btn = page.query_selector('button:has-text("Log")')

            if login_btn:
                login_btn.click()
                print('   ✅ 已点击登录按钮')
            else:
                page.evaluate('''() => {
                    const btns = document.querySelectorAll('button');
                    for (const btn of btns) {
                        const t = btn.textContent.trim();
                        if (t.includes('登录') || t.includes('Sign') || t.includes('Log')) {
                            btn.click();
                            break;
                        }
                    }
                }''')
                print('   ✅ 已通过 JS 点击登录按钮')

        except Exception as e:
            print(f'   ⚠️ 自动填写表单失败: {e}')

        # 等待用户手动完成滑块验证和登录
        print('\n' + '=' * 60)
        print('⏳ 请在浏览器中手动完成以下操作:')
        print('   1. 如果出现滑块验证码 → 拖动图片完成验证')
        print('   2. 如果出现短信验证 → 输入验证码')
        print('   3. 确认登录成功（页面跳转到 dashboard）')
        print('=' * 60)
        print('   等待登录完成（最长 120 秒）...')

        # 等待页面跳转到 dashboard（登录成功）
        login_success = False
        try:
            page.wait_for_url('**/dashboard**', timeout=120000)
            login_success = True
            print('   ✅ 登录成功！页面已跳转到 dashboard')
        except:
            print('   ⚠️ 未检测到 dashboard 跳转')

        if not login_success:
            try:
                page.wait_for_url('**/e-commerce/**', timeout=30000)
                login_success = True
                print('   ✅ 登录成功！页面已跳转')
            except:
                pass

        if not login_success:
            print('   ⚠️ 未检测到页面跳转，继续等待 10 秒...')
            page.wait_for_timeout(10000)

        # 等待一下确保登录状态稳定
        page.wait_for_timeout(3000)

        # 获取 cookies
        cookies = context.cookies()
        print(f'   📦 获取到 {len(cookies)} 个 cookies')

        # 检查是否有登录凭证
        has_token = any(
            'token' in c['name'].lower() or 'session' in c['name'].lower()
            or 'auth' in c['name'].lower() or 'sid' in c['name'].lower()
            for c in cookies
        )
        if has_token:
            print('   ✅ Cookie 中包含登录凭证！')
        else:
            print('   ⚠️ Cookie 中未发现登录凭证，可能登录未成功')

        # 保存 cookies
        with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        print(f'   💾 Cookies 已保存到: {COOKIE_FILE}')

        # 尝试抓取数据
        print('\n📡 尝试抓取销量榜数据...')
        try:
            page.goto(
                f'https://www.fastmoss.com/zh/e-commerce/saleslist?region={REGION}&page=1&l1_cid={L1_CID}&date_type={DATE_TYPE}',
                wait_until='domcontentloaded',
                timeout=60000
            )
            page.wait_for_timeout(10000)

            body_text = page.inner_text('body')
            print(f'   页面文本长度: {len(body_text)} 字符')

            html = page.content()
            debug_path = os.path.join(SCRIPTS_DIR, 'fastmoss_after_login.html')
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f'   💾 页面源码已保存: {debug_path}')

            page.screenshot(path=os.path.join(SCRIPTS_DIR, 'fastmoss_after_login.png'))
            print(f'   📸 截图已保存')

        except Exception as e:
            print(f'   ❌ 抓取失败: {e}')

        browser.close()

    return cookies


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Fastmoss 自动登录 + 数据抓取')
    parser.add_argument('--phone', help='Fastmoss 登录手机号')
    parser.add_argument('--password', help='Fastmoss 登录密码')
    args = parser.parse_args()

    phone = args.phone
    password = args.password

    if not phone or not password:
        env_phone, env_pass = load_env_account()
        phone = phone or env_phone
        password = password or env_pass

    if not phone or not password:
        print('❌ 未提供账号密码！')
        print('   方式1: 在 .env.fastmoss 中配置 FASTMOSS_EMAIL 和 FASTMOSS_PASSWORD')
        print('   方式2: python scripts/fastmoss_login_and_fetch.py --phone 183xxxx --password xxxx')
        sys.exit(1)

    cookies = login_and_get_cookies(phone, password)

    if cookies:
        print(f'\n✅ 完成！已获取 {len(cookies)} 个 cookies')
        print(f'   Cookie 文件: {COOKIE_FILE}')
        print(f'\n现在可以运行数据抓取脚本了:')
        print(f'   python scripts/fetch_fastmoss_api.py')
    else:
        print('\n❌ 登录失败，未获取到 cookies')


if __name__ == '__main__':
    main()
