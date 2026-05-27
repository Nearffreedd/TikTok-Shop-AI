"""
智能数据导入调度器
功能：自动识别 Layer2_Working 中的新 Excel 文件，判断类型并执行对应导入流程

文件类型识别规则：
  *商品数据 -> import_weekly_data.py（商品周数据）
  *店铺数据 -> import_shop_weekly.py（店铺周数据）
  *视频数据 -> （预留）
  *联盟数据 -> （预留）

用法：
  python scripts/auto_import.py                          # 扫描 Layer2_Working 所有新文件
  python scripts/auto_import.py "文件名关键词"            # 导入匹配的文件
  python scripts/auto_import.py --all                     # 导入所有未导入的文件
  python scripts/auto_import.py --status                  # 查看已导入的文件记录
"""

import os
import sys
import re
import json
import subprocess
from datetime import datetime

# 路径配置
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAYER2_DIR = os.path.join(BASE_DIR, 'Layer2_Working')
SCRIPTS_DIR = os.path.join(BASE_DIR, 'scripts')
DB_PATH = os.path.join(BASE_DIR, 'Layer1_Permanent', '01_My_Shop', 'shop_data.db')
IMPORT_LOG = os.path.join(BASE_DIR, 'Layer1_Permanent', '01_My_Shop', 'import_log.json')
BACKUP_BASE = os.path.join(BASE_DIR, 'Layer1_Permanent', '01_My_Shop', 'Backups')

# 文件类型映射
FILE_TYPES = {
    '商品数据': {
        'script': 'import_weekly_data.py',
        'pattern': r'([A-Z]+)-商品数据',
        'description': '商品周数据'
    },
    '店铺数据': {
        'script': 'import_shop_weekly.py',
        'pattern': r'([A-Z]+)-店铺数据',
        'description': '店铺周数据'
    },
    'Product campaign data': {
        'script': 'import_gmvmax.py',
        'pattern': r'^([A-Z]*)\s*Product campaign data',
        'description': 'GMV MAX 广告投放数据'
    },
    '联盟数据': {
        'script': 'import_affiliate_data.py',
        'pattern': r'ListProducts_.*ALLPlan',
        'description': '联盟推广数据',
        'shop_code_fixed': 'PNB'  # 固定店铺代码
    },
}


def load_import_log():
    """加载导入记录"""
    if os.path.exists(IMPORT_LOG):
        with open(IMPORT_LOG, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'imported_files': [], 'last_scan': None}


def save_import_log(log):
    """保存导入记录"""
    os.makedirs(os.path.dirname(IMPORT_LOG), exist_ok=True)
    with open(IMPORT_LOG, 'w', encoding='utf-8') as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def detect_file_type(filename):
    """识别文件类型，返回 (type_key, shop_code, script_name) 或 None"""
    for type_key, config in FILE_TYPES.items():
        if type_key in filename:
            match = re.match(config['pattern'], filename)
            if match:
                # 如果配置了固定店铺代码，使用固定值
                if 'shop_code_fixed' in config:
                    shop_code = config['shop_code_fixed']
                else:
                    shop_code = match.group(1)
                return type_key, shop_code, config['script']
    return None


def scan_new_files():
    """扫描 Layer2_Working 中所有 Excel 文件"""
    log = load_import_log()
    imported_set = set(log['imported_files'])

    new_files = []
    if not os.path.exists(LAYER2_DIR):
        print(f'[X] 目录不存在: {LAYER2_DIR}')
        return new_files

    for f in os.listdir(LAYER2_DIR):
        if not f.endswith('.xlsx'):
            continue

        filepath = os.path.join(LAYER2_DIR, f)
        file_info = {
            'filename': f,
            'filepath': filepath,
            'mtime': os.path.getmtime(filepath),
            'size': os.path.getsize(filepath)
        }

        # 检测文件类型
        type_info = detect_file_type(f)
        if type_info:
            file_info['type_key'] = type_info[0]
            file_info['shop_code'] = type_info[1]
            file_info['script'] = type_info[2]
            file_info['description'] = FILE_TYPES[type_info[0]]['description']
        else:
            file_info['type_key'] = '未知'
            file_info['shop_code'] = None
            file_info['script'] = None
            file_info['description'] = '未识别的文件类型'

        # 检查是否已导入
        if f in imported_set:
            file_info['status'] = '[OK] 已导入'
        else:
            file_info['status'] = '[NEW] 待导入'
            new_files.append(file_info)

        file_info['mtime_str'] = datetime.fromtimestamp(file_info['mtime']).strftime('%Y-%m-%d %H:%M')

    return new_files


def import_file(file_info):
    """导入单个文件"""
    filename = file_info['filename']
    filepath = file_info['filepath']
    script = file_info['script']
    shop_code = file_info['shop_code']

    if not script:
        print(f'[X] 无法识别文件类型: {filename}')
        return False

    script_path = os.path.join(SCRIPTS_DIR, script)
    if not os.path.exists(script_path):
        print(f'[X] 脚本不存在: {script_path}')
        return False

    print(f'\n{"="*50}')
    print(f'[IN] 开始导入: {filename}')
    print(f'[INFO] 类型: {file_info["description"]}')
    print(f'[SHOP] 店铺: {shop_code}')
    print(f'{"="*50}')

    # 执行导入脚本
    result = subprocess.run(
        ['python', script_path, filepath, shop_code],
        capture_output=True, text=True, cwd=BASE_DIR
    )

    print(result.stdout)
    if result.stderr:
        print(f'[WARN] 错误: {result.stderr}')

    success = '[完成]' in result.stdout or '导入完成' in result.stdout

    # 记录导入日志
    log = load_import_log()
    if filename not in log['imported_files']:
        log['imported_files'].append(filename)
    log['last_scan'] = datetime.now().isoformat()
    save_import_log(log)

    # 导入成功后，将源文件移动到备份目录
    if success:
        backup_dir = os.path.join(BACKUP_BASE, shop_code, file_info['type_key'])
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = os.path.join(backup_dir, filename)

        # 如果备份目录已有同名文件，加时间戳后缀
        if os.path.exists(backup_path):
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            name_part, ext = os.path.splitext(filename)
            backup_path = os.path.join(backup_dir, f'{name_part}_{ts}{ext}')

        try:
            os.rename(filepath, backup_path)
            print(f'[BACKUP] 已备份到: {backup_path}')
        except Exception as e:
            print(f'[WARN] 备份失败: {e}')

    return success


def show_status():
    """显示所有文件状态"""
    log = load_import_log()
    imported_set = set(log['imported_files'])

    print(f'\n[STATS] 数据导入状态总览')
    print(f'{"="*60}')
    print(f'{"文件名":<45} {"类型":<12} {"状态":<10}')
    print(f'{"-"*60}')

    if not os.path.exists(LAYER2_DIR):
        print('目录不存在')
        return

    for f in sorted(os.listdir(LAYER2_DIR)):
        if not f.endswith('.xlsx'):
            continue

        type_info = detect_file_type(f)
        if type_info:
            type_name = type_info[0]
        else:
            type_name = '未知'

        status = '[OK] 已导入' if f in imported_set else '[NEW] 待导入'
        name_display = f[:42] + '...' if len(f) > 42 else f
        print(f'{name_display:<45} {type_name:<12} {status:<10}')

    print(f'{"-"*60}')
    print(f'已导入: {len(imported_set)} 个文件')
    print(f'待导入: {len(scan_new_files())} 个文件')


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--status':
        show_status()
        return

    if len(sys.argv) > 1 and sys.argv[1] == '--all':
        # 导入所有待导入文件
        new_files = scan_new_files()
        if not new_files:
            print('[OK] 没有新的文件需要导入')
            return

        print(f'[PACK] 发现 {len(new_files)} 个新文件，开始批量导入...')
        success_count = 0
        for f in new_files:
            if import_file(f):
                success_count += 1

        print(f'\n{"="*50}')
        print(f'[STATS] 批量导入完成: {success_count}/{len(new_files)} 成功')
        return

    if len(sys.argv) > 1:
        # 按关键词匹配导入
        keyword = sys.argv[1]
        new_files = scan_new_files()
        matched = [f for f in new_files if keyword.lower() in f['filename'].lower()]

        if not matched:
            # 也搜索已导入的文件
            all_files = []
            for f in os.listdir(LAYER2_DIR):
                if f.endswith('.xlsx') and keyword.lower() in f.lower():
                    type_info = detect_file_type(f)
                    if type_info:
                        all_files.append({
                            'filename': f,
                            'filepath': os.path.join(LAYER2_DIR, f),
                            'type_key': type_info[0],
                            'shop_code': type_info[1],
                            'script': type_info[2],
                            'description': FILE_TYPES[type_info[0]]['description']
                        })

            if all_files:
                print(f'[SEARCH] 找到 {len(all_files)} 个匹配文件（可能已导入）')
                for f in all_files:
                    print(f'  {f["filename"]} ({f["description"]})')
                print('\n如需重新导入，请使用完整路径')
            else:
                print(f'[X] 未找到匹配 "{keyword}" 的文件')
            return

        for f in matched:
            import_file(f)
        return

    # 默认：扫描并显示新文件
    new_files = scan_new_files()

    print(f'\n[SEARCH] 扫描 Layer2_Working/ 中的 Excel 文件...')
    print(f'{"="*60}')

    if not new_files:
        print('[OK] 没有新的文件需要导入')
        show_status()
        return

    print(f'[PACK] 发现 {len(new_files)} 个新文件:\n')

    for f in new_files:
        print(f'  [FILE] {f["filename"]}')
        print(f'     [INFO] {f["description"]} | [SHOP] {f["shop_code"]} | [TIME] {f["mtime_str"]}')
        print()

    print('[TIP] 使用以下命令导入:')
    print(f'  python scripts/auto_import.py --all          # 导入全部')
    for f in new_files:
        keyword = f['filename'].replace('.xlsx', '')[:20]
        print(f'  python scripts/auto_import.py "{keyword}"  # 导入 {f["filename"]}')
    print(f'  python scripts/auto_import.py --status       # 查看状态')


if __name__ == '__main__':
    main()
