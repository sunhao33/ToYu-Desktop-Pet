# Fix quadruple quotes
with open('ui/main_window.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace quadruple quotes with triple quotes
content = content.replace('""""', '"""')

with open('ui/main_window.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed quadruple quotes')
