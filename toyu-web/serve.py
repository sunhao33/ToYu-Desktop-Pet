"""本地预览服务器（仅用于开发预览，正式部署用静态托管）。

零依赖，只用标准库。默认端口 8899，自动避开被占用的端口。
用法：
    python serve.py            # 起服务并打印地址
    python serve.py 9000       # 指定端口
"""

import http.server
import os
import socket
import socketserver
import sys
import threading
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def end_headers(self):
        # 开发预览时不要缓存，改完刷新就能看到
        self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

    def log_message(self, fmt, *args):
        # 只打印错误，别刷屏
        if args and str(args[1]).startswith(("4", "5")):
            sys.stderr.write("  %s %s\n" % (self.address_string(), fmt % args))


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def pick_port(preferred):
    for port in [preferred] + list(range(preferred + 1, preferred + 40)):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise SystemExit("找不到可用端口")


def main():
    wanted = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
    port = pick_port(wanted)
    url = "http://127.0.0.1:%d/" % port
    with Server(("127.0.0.1", port), Handler) as httpd:
        print("ToYu 宣传站本地预览")
        print("  目录: %s" % ROOT)
        print("  地址: %s" % url)
        print("  停止: Ctrl+C")
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止")


if __name__ == "__main__":
    main()
