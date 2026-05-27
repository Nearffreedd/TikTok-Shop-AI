import sys, os, json, requests

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COOKIE_FILE = os.path.join(BASE_DIR, 'scripts', 'fastmoss_cookies.json')

with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
    cookies_list = json.load(f)
cookies_dict = {c['name']: c['value'] for c in cookies_list}

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'https://www.fastmoss.com/zh/e-commerce/saleslist',
    'Origin': 'https://www.fastmoss.com',
}

# 测试所有类目
for cid in ["1", "3", "8"]:
    print(f"\n=== Category {cid} ===")
    params = {'page': '1', 'pagesize': '10', 'order': '1,2', 'region': 'PH', 'l1_cid': cid, 'date_type': '1'}
    resp = requests.get('https://www.fastmoss.com/api/goods/saleRank', params=params, cookies=cookies_dict, headers=headers, timeout=15)
    print(f'Status: {resp.status_code}')
    print(f'Content-Type: {resp.headers.get("Content-Type", "")}')
    raw = resp.json()
    print(f'Type: {type(raw).__name__}')
    if isinstance(raw, dict):
        print(f'Keys: {list(raw.keys())}')
        rl = raw.get('data', {}).get('rank_list', [])
        print(f'rank_list: {len(rl)} items')
    elif isinstance(raw, list):
        print(f'List: {len(raw)} items')
        if raw:
            print(f'First type: {type(raw[0]).__name__}')
            print(f'First: {json.dumps(raw[0], ensure_ascii=False)[:200]}')
    else:
        print(f'Unexpected type: {type(raw).__name__}')
        print(f'Value: {str(raw)[:200]}')
