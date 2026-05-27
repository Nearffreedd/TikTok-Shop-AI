import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

# 模拟 fetch_fastmoss_api.py 的导入顺序
import os, sys, json, re, sqlite3, requests
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

print(f'requests type: {type(requests)}')
print(f'requests module: {getattr(requests, "__file__", "N/A")}')
print(f'requests has get: {hasattr(requests, "get")}')
print(f'requests.get type: {type(requests.get)}')

# 测试实际调用
cookies_dict = {}
COOKIE_FILE = os.path.join('scripts', 'fastmoss_cookies.json')
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

params = {'page': '1', 'pagesize': '10', 'order': '1,2', 'region': 'PH', 'l1_cid': '8', 'date_type': '1'}
resp = requests.get('https://www.fastmoss.com/api/goods/saleRank', params=params, cookies=cookies_dict, headers=headers, timeout=15)
print(f'Status: {resp.status_code}')
raw = resp.json()
print(f'Type: {type(raw).__name__}')
if isinstance(raw, dict):
    print(f'Keys: {list(raw.keys())}')
    rl = raw.get('data', {}).get('rank_list', [])
    print(f'rank_list: {len(rl)} items')
elif isinstance(raw, list):
    print(f'List: {len(raw)} items')
