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

# 测试 pagesize=50 的情况
for cid in ["1", "3", "8"]:
    print(f"\n=== Category {cid} (pagesize=50) ===")
    params = {'page': '1', 'pagesize': '50', 'order': '1,2', 'region': 'PH', 'l1_cid': cid, 'date_type': '1'}
    resp = requests.get('https://www.fastmoss.com/api/goods/saleRank', params=params, cookies=cookies_dict, headers=headers, timeout=15)
    print(f'Status: {resp.status_code}')
    raw = resp.json()
    print(f'Type: {type(raw).__name__}')
    if isinstance(raw, dict):
        print(f'Keys: {list(raw.keys())}')
        print(f'code: {raw.get("code")}')
        print(f'msg: {raw.get("msg")}')
        df = raw.get('data')
        print(f'data type: {type(df).__name__}')
        if isinstance(df, dict):
            print(f'data keys: {list(df.keys())}')
            rl = df.get('rank_list', [])
            print(f'rank_list: {len(rl)} items')
        elif isinstance(df, list):
            print(f'data is list: {len(df)} items')
        else:
            print(f'data value: {str(df)[:200]}')
    elif isinstance(raw, list):
        print(f'List: {len(raw)} items')
