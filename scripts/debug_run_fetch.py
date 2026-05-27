import sys, traceback
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

# 直接导入并运行 fetch_fastmoss_api 的 fetch_saleslist_via_api
from scripts.fetch_fastmoss_api import fetch_saleslist_via_api, ensure_db_tables, save_to_database, generate_industry_report

try:
    products = fetch_saleslist_via_api(category_id="8")
    print(f"\nProducts returned: {len(products)}")
    if products:
        print(f"First product: {products[0]}")
except Exception as e:
    traceback.print_exc()
