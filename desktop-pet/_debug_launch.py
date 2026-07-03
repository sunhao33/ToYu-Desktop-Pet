import sys, traceback, os

log_path = os.path.join(os.path.dirname(__file__), '_crash.log')

try:
    import main
except Exception:
    with open(log_path, 'w', encoding='utf-8') as f:
        traceback.print_exc(file=f)
    sys.exit(1)
