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

# 测试 pagesize=10
params = {'page': '1', 'pagesize': '10', 'order': '1,2', 'region': 'PH', 'l1_cid': '8', 'date_type': '1'}
resp = requests.get('https://www.fastmoss.com/api/goods/saleRank', params=params, cookies=cookies_dict, headers=headers, timeout=15)
raw = resp.json()
print(f'code: {raw.get("code")}')
print(f'msg: {raw.get("msg")}')
print(f'data type: {type(raw.get("data")).__name__}')
if isinstance(raw.get('data'), dict):
    print(f'data keys: {list(raw.get("data", {}).keys())}')
    rl = raw.get('data', {}).get('rank_list', [])
    print(f'rank_list: {len(rl)} items')
