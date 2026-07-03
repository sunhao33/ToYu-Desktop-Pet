import subprocess
import sys

proc = subprocess.Popen(
    [r"C:\Users\34338\Desktop\003\desktop-pet\dist\ToYu.exe"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    creationflags=subprocess.CREATE_NO_WINDOW
)

import time
time.sleep(8)

if proc.poll() is not None:
    stdout = proc.stdout.read().decode('utf-8', errors='replace')
    stderr = proc.stderr.read().decode('utf-8', errors='replace')
    print(f"Exit code: {proc.returncode}")
    print(f"STDOUT: {stdout[:2000]}")
    print(f"STDERR: {stderr[:2000]}")
else:
    print("Process still running (no crash)")
    proc.terminate()
