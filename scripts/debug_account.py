"""
检查 Fastmoss 账号状态和 MSG_SAFE_0001 详情
"""
import sys, os, json
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

# 1. 检查用户信息
print("=== 用户信息 ===")
resp = requests.get('https://www.fastmoss.com/api/user/index/userInfo', cookies=cookies_dict, headers=headers, timeout=15)
print(json.dumps(resp.json(), ensure_ascii=False, indent=2)[:500])

# 2. 检查会员状态
print("\n=== 会员状态 ===")
resp = requests.get('https://www.fastmoss.com/api/user/userPayTrial', cookies=cookies_dict, headers=headers, timeout=15)
print(json.dumps(resp.json(), ensure_ascii=False, indent=2)[:500])

# 3. 检查 MSG_SAFE_0001 详情 - 尝试不同的 pagesize
print("\n=== 测试不同 pagesize ===")
for ps in [5, 10, 20, 50, 100]:
    params = {'page': '1', 'pagesize': str(ps), 'order': '1,2', 'region': 'PH', 'l1_cid': '8', 'date_type': '1'}
    resp = requests.get('https://www.fastmoss.com/api/goods/saleRank', params=params, cookies=cookies_dict, headers=headers, timeout=15)
    data = resp.json()
    print(f"  pagesize={ps}: code={data.get('code')}, data={data.get('data')}")

# 4. 检查是否有其他可用的 API
print("\n=== 测试其他 API ===")
# 商品搜索 API
params2 = {'keyword': 'jewelry', 'region': 'PH', 'page': '1', 'pagesize': '10'}
resp = requests.get('https://www.fastmoss.com/api/goods/search', params=params2, cookies=cookies_dict, headers=headers, timeout=15)
print(f"  goods/search: {json.dumps(resp.json(), ensure_ascii=False)[:300]}")

# 新品榜
params3 = {'page': '1', 'pagesize': '10', 'region': 'PH', 'l1_cid': '8', 'date_type': '1'}
resp = requests.get('https://www.fastmoss.com/api/goods/newRank', params=params3, cookies=cookies_dict, headers=headers, timeout=15)
print(f"  goods/newRank: {json.dumps(resp.json(), ensure_ascii=False)[:300]}")

# 热推榜
resp = requests.get('https://www.fastmoss.com/api/goods/hotRank', params=params3, cookies=cookies_dict, headers=headers, timeout=15)
print(f"  goods/hotRank: {json.dumps(resp.json(), ensure_ascii=False)[:300]}")

# 5. 检查 captcha 配置
print("\n=== 验证码配置 ===")
resp = requests.get('https://www.fastmoss.com/api/captcha/config', cookies=cookies_dict, headers=headers, timeout=15)
print(json.dumps(resp.json(), ensure_ascii=False)[:500])
