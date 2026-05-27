"""检查 Fastmoss 登录状态"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fix_encoding
import json, urllib.request, ssl

# 加载 cookies
cookie_path = os.path.join(os.path.dirname(__file__), 'fastmoss_cookies.json')
with open(cookie_path, 'r', encoding='utf-8') as f:
    cookies = json.load(f)
cookie_str = '; '.join([f'{c["name"]}={c["value"]}' for c in cookies])

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = {
    'Cookie': cookie_str,
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
}

print('=' * 60)
print('🔍 Fastmoss 登录状态检查')
print('=' * 60)

# 检查 cookie 中是否有登录 token
print('\n📋 Cookie 分析:')
has_token = False
for c in cookies:
    name = c['name']
    if any(kw in name.lower() for kw in ['token', 'session', 'auth', 'login', 'access', 'jwt', 'sid']):
        print(f'  ✅ 发现登录凭证: {name} = {c["value"][:30]}...')
        has_token = True

if not has_token:
    print('  ⚠️  未发现登录凭证（token/session/auth）')
    print('  💡 当前 cookies 仅包含: 分析追踪(GA/Clarity)、语言偏好、地区设置')
    print('  💡 说明：销量榜 API 可能不需要登录即可访问')

# 测试1: 用户信息接口
print('\n📡 测试1: 用户信息接口 (需要登录)')
try:
    req = urllib.request.Request('https://www.fastmoss.com/api/user/info', headers=headers)
    resp = urllib.request.urlopen(req, context=ctx, timeout=10)
    data = json.loads(resp.read().decode('utf-8'))
    code = data.get('code')
    if code == 0 or code == 200:
        print(f'  ✅ 登录成功！用户信息: {json.dumps(data, ensure_ascii=False)[:200]}')
    else:
        print(f'  ❌ 未登录或登录失效: code={code}, msg={data.get("msg", "")}')
except Exception as e:
    print(f'  ❌ 请求失败: {e}')

# 测试2: 销量榜接口 (公开数据)
print('\n📡 测试2: 销量榜接口 (公开数据)')
try:
    url = 'https://www.fastmoss.com/api/goods/saleRank?page=1&pagesize=3&order=1,2&region=PH&l1_cid=8&date_type=1&date_value=2026-05-26'
    req = urllib.request.Request(url, headers=headers)
    resp = urllib.request.urlopen(req, context=ctx, timeout=10)
    data = json.loads(resp.read().decode('utf-8'))
    code = data.get('code')
    rank_list = data.get('data', {}).get('rank_list', [])
    print(f'  状态码: {code}, 数据条数: {len(rank_list)}')
    if rank_list:
        print(f'  ✅ 成功获取数据！')
        print(f'  第一条: {rank_list[0]["title"][:60]}')
        print(f'  日销: {rank_list[0]["sold_count"]}, 日销售额: PHP {rank_list[0]["sale_amount"]:,.0f}')
    else:
        print(f'  ⚠️  返回空数据')
except Exception as e:
    print(f'  ❌ 请求失败: {e}')

# 测试3: 达人分析接口 (可能需要登录)
print('\n📡 测试3: 达人分析接口 (可能需要登录)')
try:
    url = 'https://www.fastmoss.com/api/author/rank?page=1&pagesize=3&region=PH&date_type=1&date_value=2026-05-26'
    req = urllib.request.Request(url, headers=headers)
    resp = urllib.request.urlopen(req, context=ctx, timeout=10)
    data = json.loads(resp.read().decode('utf-8'))
    code = data.get('code')
    print(f'  状态码: {code}, 消息: {data.get("msg", "")}')
    if code == 0 or code == 200:
        print(f'  ✅ 可以访问达人数据')
    else:
        print(f'  ⚠️  需要登录才能访问')
except Exception as e:
    print(f'  ❌ 请求失败: {e}')

print('\n' + '=' * 60)
print('📌 结论:')
if has_token:
    print('  ✅ Cookie 中包含登录凭证')
else:
    print('  ⚠️  Cookie 中无登录凭证，当前为游客模式')
print('  💡 销量榜等基础数据可能无需登录即可获取')
print('  💡 达人分析、高级筛选等功能可能需要登录')
print('=' * 60)
