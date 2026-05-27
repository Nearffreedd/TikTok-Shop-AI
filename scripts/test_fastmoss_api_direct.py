"""
直接测试 Fastmoss API 调用 - 探索可用端点
"""

import os
import sys
import json
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, 'scripts')
COOKIE_FILE = os.path.join(SCRIPTS_DIR, 'fastmoss_cookies.json')

with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
    cookies_list = json.load(f)

cookies_dict = {}
for c in cookies_list:
    cookies_dict[c['name']] = c['value']

print(f"Loaded {len(cookies_dict)} cookies")

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'https://www.fastmoss.com/zh/e-commerce/saleslist',
    'Origin': 'https://www.fastmoss.com',
}

# 测试各种可能的 API 端点
endpoints = [
    # 商品相关
    ("GET", "https://www.fastmoss.com/api/goods/saleRank", {"page": "1", "pagesize": "10", "region": "PH", "l1_cid": "8", "date_type": "1", "order": "1,2"}),
    ("GET", "https://www.fastmoss.com/api/goods/saleRank", {"page": "1", "pagesize": "10", "region": "PH", "l1_cid": "8", "date_type": "2", "order": "1,2"}),
    # 尝试不同的 order 参数
    ("GET", "https://www.fastmoss.com/api/goods/saleRank", {"page": "1", "pagesize": "10", "region": "PH", "l1_cid": "8", "date_type": "1", "order": "1"}),
    ("GET", "https://www.fastmoss.com/api/goods/saleRank", {"page": "1", "pagesize": "10", "region": "PH", "l1_cid": "8", "date_type": "1", "order": "2"}),
    # 达人相关
    ("GET", "https://www.fastmoss.com/api/author/index/list", {"pagesize": "10", "region": "PH"}),
    ("GET", "https://www.fastmoss.com/api/author/index/country", {"pagesize": "100"}),
    # 店铺相关
    ("GET", "https://www.fastmoss.com/api/shop/index/list", {"pagesize": "10", "region": "PH"}),
    # 搜索
    ("GET", "https://www.fastmoss.com/api/search/product", {"keyword": "jewelry", "region": "PH", "pagesize": "10"}),
    ("GET", "https://www.fastmoss.com/api/search/product", {"keyword": "necklace", "region": "PH", "pagesize": "10"}),
    # 类目
    ("GET", "https://www.fastmoss.com/api/goods/category", {"region": "PH"}),
    # 热销
    ("GET", "https://www.fastmoss.com/api/goods/hot", {"region": "PH", "pagesize": "10"}),
    # 趋势
    ("GET", "https://www.fastmoss.com/api/goods/trend", {"region": "PH", "pagesize": "10"}),
    # 视频
    ("GET", "https://www.fastmoss.com/api/video/list", {"region": "PH", "pagesize": "10"}),
    # 直播
    ("GET", "https://www.fastmoss.com/api/live/list", {"region": "PH", "pagesize": "10"}),
    # 联盟
    ("GET", "https://www.fastmoss.com/api/affiliate/list", {"region": "PH", "pagesize": "10"}),
    # 商品详情
    ("GET", "https://www.fastmoss.com/api/goods/detail", {"product_id": "test", "region": "PH"}),
    # 用户信息
    ("GET", "https://www.fastmoss.com/api/user/index/userInfo", {}),
    ("GET", "https://www.fastmoss.com/api/user/user", {}),
]

for method, url, params in endpoints:
    print(f"\n--- Testing: {url.split('/api/')[1]} ---")
    print(f"  Params: {params}")
    try:
        if method == "GET":
            resp = requests.get(url, params=params, cookies=cookies_dict, headers=headers, timeout=15)
        else:
            resp = requests.post(url, json=params, cookies=cookies_dict, headers=headers, timeout=15)

        print(f"  Status: {resp.status_code}")

        try:
            data = resp.json()
            code = data.get('code', 'N/A')
            msg = data.get('msg', 'N/A')
            d = data.get('data', 'N/A')
            ext = data.get('ext', {})

            if isinstance(d, list):
                print(f"  Code: {code}, Items: {len(d)}, is_login: {ext.get('is_login', 'N/A')}")
                if d and len(d) > 0:
                    print(f"  First item keys: {list(d[0].keys()) if isinstance(d[0], dict) else type(d[0])}")
            elif isinstance(d, dict):
                # 看看 dict 里有哪些 key 是列表
                list_keys = [k for k, v in d.items() if isinstance(v, list)]
                print(f"  Code: {code}, Dict keys: {list(d.keys())}, List keys: {list_keys}, is_login: {ext.get('is_login', 'N/A')}")
                if list_keys:
                    for lk in list_keys:
                        print(f"    {lk}: {len(d[lk])} items")
                        if d[lk] and len(d[lk]) > 0:
                            print(f"      First item: {json.dumps(d[lk][0], ensure_ascii=False)[:200]}")
            else:
                print(f"  Code: {code}, Data: {str(d)[:200]}, is_login: {ext.get('is_login', 'N/A')}")
        except:
            print(f"  Raw: {resp.text[:200]}")

    except Exception as e:
        print(f"  FAILED: {e}")

print("\nDone")
