import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open('scripts/fastmoss_cookies.json', 'r', encoding='utf-8') as f:
    cookies = json.load(f)

print(f'Cookie 数量: {len(cookies)}')
for c in cookies:
    print(f'  {c["name"]}: {c["value"][:40]}...')
