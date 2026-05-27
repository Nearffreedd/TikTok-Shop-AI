"""
fix_encoding.py — Windows GBK 编码修复模块

在 Windows 终端（cmd）下，Python 默认使用 GBK 编码输出，
导致 emoji、₱（菲律宾比索符号）等 Unicode 字符报错：
    UnicodeEncodeError: 'gbk' codec can't encode character

使用方法：在任何脚本开头 import fix_encoding 即可自动修复。

示例：
    import fix_encoding  # 放在文件最顶部
    print("✅ 测试 emoji ₱ 菲律宾比索")  # 不再报错

原理：将 sys.stdout / sys.stderr 的编码强制锁定为 UTF-8，
      完全绕过 Windows 终端默认的 GBK 编码。
"""

import sys
import io

# 强制 stdout/stderr 使用 UTF-8 编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
