import sys, marshal, types

pyc_path = r'C:\Users\34338\Desktop\003\desktop-pet\pet_engine\__pycache__\pet_window.cpython-314.pyc'
with open(pyc_path, 'rb') as f:
    f.read(16)
    code = marshal.load(f)

for const in code.co_consts:
    if isinstance(const, types.CodeType) and const.co_name == 'PetWindow':
        cls_code = const
        break

pyc_methods = set()
for const in cls_code.co_consts:
    if isinstance(const, types.CodeType):
        pyc_methods.add(const.co_name)

# Check which methods exist in current file
with open(r'C:\Users\34338\Desktop\003\desktop-pet\pet_engine\pet_window.py', 'r', encoding='utf-8') as f:
    src = f.read()

import re
src_methods = set(re.findall(r'def (\w+)\(self', src))

missing = pyc_methods - src_methods - {'__annotate__'}
extra = src_methods - pyc_methods

if missing:
    print("MISSING from source (in .pyc but not in .py):")
    for m in sorted(missing):
        print(f"  - {m}")
if extra:
    print("EXTRA in source (in .py but not in .pyc):")
    for m in sorted(extra):
        print(f"  + {m}")
if not missing and not extra:
    print("All methods match!")
