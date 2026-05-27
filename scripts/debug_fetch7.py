import sys, os, json, requests
sys.stdout.reconfigure(encoding='utf-8')

with open('scripts/fastmoss_cookies.json', 'r', encoding='utf-8') as f:
    cookies_list = json.load(f)
cookies_dict = {c['name']: c['value'] for c in cookies_list}

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'https://www.fastmoss.com/zh/e-commerce/saleslist',
    'Origin': 'https://www.fastmoss.com',
}

# 测试 debug_fetch2.py 的解析方式
params = {'page': '1', 'pagesize': '10', 'order': '1,2', 'region': 'PH', 'l1_cid': '8', 'date_type': '1'}
resp = requests.get('https://www.fastmoss.com/api/goods/saleRank', params=params, cookies=cookies_dict, headers=headers, timeout=15)
raw = resp.json()

print(f'Full response:')
print(json.dumps(raw, ensure_ascii=False, indent=2)[:1000])

print(f'\n---')
print(f'raw type: {type(raw).__name__}')
if isinstance(raw, dict):
    print(f'keys: {list(raw.keys())}')
    data = raw.get('data', {})
    print(f'data type: {type(data).__name__}')
    if isinstance(data, dict):
        print(f'data keys: {list(data.keys())}')
        rl = data.get('rank_list', [])
        print(f'rank_list: {len(rl)} items')
        if rl:
            print(f'First item: {json.dumps(rl[0], ensure_ascii=False)[:300]}')
