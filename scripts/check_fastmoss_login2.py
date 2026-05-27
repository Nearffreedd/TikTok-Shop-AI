"""深入诊断 Fastmoss API 接口"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fix_encoding
import json, urllib.request, ssl

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

# 尝试不同的 API 路径
test_urls = [
    # 销量榜 - 不同路径
    ('销量榜 v1', 'https://www.fastmoss.com/api/goods/saleRank?page=1&pagesize=3&order=1,2&region=PH&l1_cid=8&date_type=1&date_value=2026-05-26'),
    ('销量榜 v2', 'https://www.fastmoss.com/api/v1/goods/saleRank?page=1&pagesize=3&order=1,2&region=PH&l1_cid=8&date_type=1&date_value=2026-05-26'),
    ('销量榜 v3', 'https://www.fastmoss.com/api/v2/goods/saleRank?page=1&pagesize=3&order=1,2&region=PH&l1_cid=8&date_type=1&date_value=2026-05-26'),
    # 商品详情
    ('商品详情', 'https://www.fastmoss.com/api/goods/detail?product_id=1732701246104110537&region=PH'),
    # 首页
    ('首页', 'https://www.fastmoss.com/api/index'),
    # 搜索
    ('搜索', 'https://www.fastmoss.com/api/goods/search?keyword=bracelet&region=PH&page=1&pagesize=3'),
]

print('=' * 60)
print('🔍 Fastmoss API 接口诊断')
print('=' * 60)

for name, url in test_urls:
    print(f'\n📡 {name}:')
    print(f'   URL: {url}')
    try:
        req = urllib.request.Request(url, headers=headers)
        resp = urllib.request.urlopen(req, context=ctx, timeout=10)
        raw = resp.read().decode('utf-8')
        data = json.loads(raw)
        code = data.get('code', 'N/A')
        msg = data.get('msg', '')
        print(f'   状态码: {code}')
        if msg:
            print(f'   消息: {msg}')
        # 检查是否有数据
        if 'data' in data:
            d = data['data']
            if isinstance(d, dict):
                keys = list(d.keys())[:5]
                print(f'   数据字段: {keys}')
                if 'rank_list' in d:
                    print(f'   商品数: {len(d["rank_list"])}')
                    if d['rank_list']:
                        print(f'   ✅ 成功！第一条: {d["rank_list"][0]["title"][:50]}')
            elif isinstance(d, list):
                print(f'   数据条数: {len(d)}')
                if d:
                    print(f'   ✅ 成功！')
        else:
            print(f'   原始响应前200字: {raw[:200]}')
    except Exception as e:
        print(f'   ❌ 失败: {e}')

print('\n' + '=' * 60)
