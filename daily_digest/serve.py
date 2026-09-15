"""本地静态服务器：把 output/ 目录通过局域网暴露出来，手机同 WiFi 即可访问。

用法：
  python serve.py                # 默认 8080 端口，服务 output/ 目录
  python serve.py 9000           # 指定端口
  python serve.py 8080 output    # 指定端口与目录
"""
import os
import sys
import socket
import http.server
import socketserver
from functools import partial

BASE = os.path.dirname(os.path.abspath(__file__))


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    directory = sys.argv[2] if len(sys.argv) > 2 else os.path.join(BASE, "output")
    os.chdir(BASE)
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=directory)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", port), handler) as httpd:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:  # noqa: BLE001
            ip = "127.0.0.1"
        print(f"本机访问:   http://127.0.0.1:{port}")
        print(f"手机访问:   http://{ip}:{port}   （手机需与电脑同一 WiFi）")
        print("按 Ctrl+C 停止。")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止。")


if __name__ == "__main__":
    main()
