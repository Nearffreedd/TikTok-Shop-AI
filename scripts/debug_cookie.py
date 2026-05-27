import sys, os, json, requests
sys.stdout.reconfigure(encoding='utf-8')

with open('scripts/fastmoss_cookies.json', 'r', encoding='utf-8') as f:
    cookies_list = json.load(f)
cookies_dict = {c['name']: c['value'] for c in cookies_list}

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'https://www.fastmoss.com/',
    'Origin': 'https://www.fastmoss.com',
}

# 检查用户信息 API
resp = requests.get('https://www.fastmoss.com/api/user/user', cookies=cookies_dict, headers=headers, timeout=15)
raw = resp.json()
print(f'User API: {json.dumps(raw, ensure_ascii=False)[:500]}')

# 检查用户信息 API 2
resp2 = requests.get('https://www.fastmoss.com/api/user/index/userInfo', cookies=cookies_dict, headers=headers, timeout=15)
raw2 = resp2.json()
print(f'UserInfo API: {json.dumps(raw2, ensure_ascii=False)[:500]}')
