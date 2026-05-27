import sys, os, json, requests

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COOKIE_FILE = os.path.join(BASE_DIR, 'scripts', 'fastmoss_cookies.json')

with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
    cookies_list = json.load(f)
cookies_dict = {c['name']: c['value'] for c in cookies_list}
print(f'Cookies: {len(cookies_dict)}')

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'https://www.fastmoss.com/zh/e-commerce/saleslist',
    'Origin': 'https://www.fastmoss.com',
}

params = {'page': '1', 'pagesize': '10', 'order': '1,2', 'region': 'PH', 'l1_cid': '8', 'date_type': '1'}
resp = requests.get('https://www.fastmoss.com/api/goods/saleRank', params=params, cookies=cookies_dict, headers=headers, timeout=15)
print(f'Status: {resp.status_code}')
data = resp.json()
print(f'Type: {type(data).__name__}')
if isinstance(data, dict):
    print(f'Keys: {list(data.keys())}')
    rank_list = data.get('data', {}).get('rank_list', [])
    print(f'rank_list: {len(rank_list)} items')
    if rank_list:
        print(f'First item: {json.dumps(rank_list[0], ensure_ascii=False)[:300]}')
elif isinstance(data, list):
    print(f'List length: {len(data)}')
    if data:
        print(f'First: {str(data[0])[:200]}')
