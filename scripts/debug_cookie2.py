import sys, json
sys.stdout.reconfigure(encoding='utf-8')

with open('scripts/fastmoss_cookies.json', 'r', encoding='utf-8') as f:
    cookies = json.load(f)

names = [c['name'] for c in cookies]
print(f'Cookie names ({len(cookies)}):')
for n in names:
    print(f'  - {n}')

print()
for c in cookies:
    if any(k in c['name'].lower() for k in ['token', 'session', 'auth', 'sid', 'csrf', 'nonce', 'key']):
        print(f'  {c["name"]}: {c["value"][:80]}...')
