"""
尝试使用 _time 和 cnonce 参数调用 Fastmoss API
"""
import sys, os, json, time, random
sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, 'scripts')
COOKIE_FILE = os.path.join(SCRIPTS_DIR, 'fastmoss_cookies.json')

with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
    cookies_list = json.load(f)
cookies_dict = {c['name']: c['value'] for c in cookies_list}

import requests

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'https://www.fastmoss.com/zh/e-commerce/saleslist',
    'Origin': 'https://www.fastmoss.com',
}

# 生成 _time 和 cnonce
now = int(time.time())
cnonce = str(random.randint(10000000, 99999999))

print(f"_time: {now}")
print(f"cnonce: {cnonce}")

# 尝试带 _time 和 cnonce 的请求
params = {
    'page': '1',
    'pagesize': '10',
    'order': '1,2',
    'region': 'PH',
    'l1_cid': '8',
    'date_type': '1',
    '_time': str(now),
    'cnonce': cnonce,
}

print(f"\n=== 带 _time 和 cnonce 的请求 ===")
resp = requests.get('https://www.fastmoss.com/api/goods/saleRank', params=params, cookies=cookies_dict, headers=headers, timeout=15)
data = resp.json()
print(f"code: {data.get('code')}")
print(f"msg: {data.get('msg')}")
print(f"data: {json.dumps(data.get('data'), ensure_ascii=False)[:300]}")

# 尝试带 x-requested-with 头
headers2 = headers.copy()
headers2['X-Requested-With'] = 'XMLHttpRequest'
headers2['Sec-Fetch-Dest'] = 'empty'
headers2['Sec-Fetch-Mode'] = 'cors'
headers2['Sec-Fetch-Site'] = 'same-origin'

print(f"\n=== 带额外请求头的请求 ===")
resp = requests.get('https://www.fastmoss.com/api/goods/saleRank', params=params, cookies=cookies_dict, headers=headers2, timeout=15)
data = resp.json()
print(f"code: {data.get('code')}")
print(f"msg: {data.get('msg')}")

# 尝试不带 region 参数
print(f"\n=== 不带 region 参数 ===")
params3 = {'page': '1', 'pagesize': '10', 'order': '1,2', 'l1_cid': '8', 'date_type': '1'}
resp = requests.get('https://www.fastmoss.com/api/goods/saleRank', params=params3, cookies=cookies_dict, headers=headers, timeout=15)
data = resp.json()
print(f"code: {data.get('code')}")

# 尝试使用 session
print(f"\n=== 使用 session ===")
session = requests.Session()
session.cookies.update(cookies_dict)
session.headers.update(headers)
resp = session.get('https://www.fastmoss.com/api/goods/saleRank', params=params, timeout=15)
data = resp.json()
print(f"code: {data.get('code')}")

# 尝试先访问页面再请求 API
print(f"\n=== 先访问页面再请求 API ===")
session2 = requests.Session()
session2.cookies.update(cookies_dict)
session2.headers.update(headers)
# 先访问页面
session2.get('https://www.fastmoss.com/zh/e-commerce/saleslist?region=PH&page=1&l1_cid=8&date_type=1', timeout=15)
# 再请求 API
resp = session2.get('https://www.fastmoss.com/api/goods/saleRank', params=params, timeout=15)
data = resp.json()
print(f"code: {data.get('code')}")

# 尝试使用不同的 order 参数
print(f"\n=== 不同 order 参数 ===")
for order in ['1,2', '2,1', '1', '2', '3,1']:
    params4 = {'page': '1', 'pagesize': '10', 'order': order, 'region': 'PH', 'l1_cid': '8', 'date_type': '1'}
    resp = requests.get('https://www.fastmoss.com/api/goods/saleRank', params=params4, cookies=cookies_dict, headers=headers, timeout=15)
    data = resp.json()
    print(f"  order={order}: code={data.get('code')}")
