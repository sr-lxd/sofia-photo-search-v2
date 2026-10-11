"""Safe independent start: never stops another PID or the old service."""
import configparser
import json
import os
from pathlib import Path
import socket
import subprocess
import sys


def main():
    project = Path(__file__).resolve().parent
    configuration = project / "db2_v2.ini"
    ready = project / "runtime" / "isolation_ready.json"
    if not configuration.is_file() or not ready.is_file():
        raise RuntimeError("请先运行准备照片搜索v2.py，完成独立数据库和索引准备")
    parser = configparser.ConfigParser()
    parser.read(configuration, encoding="utf-8")
    if parser.get("database", "database") != "photo_search_v2" or parser.get("auth", "cookie_name") != "photo_search_v2_auth":
        raise RuntimeError("v2隔离配置不正确")
    port = int(parser.get("server", "port"))
    if port == 5090:
        raise RuntimeError("v2不得占用原服务5090端口")
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            print(f"端口{port}已被占用，未停止任何进程。")
            return
    runtime = project / "runtime"
    log = (runtime / "server.log").open("ab")
    environment = dict(os.environ, PHOTO_SEARCH_CONFIG=str(configuration), PHOTO_SEARCH_PORT=str(port), PHOTO_SEARCH_LAZY_MODELS="1")
    python = project / ".venv" / "Scripts" / "python.exe"
    if not python.is_file():
        raise RuntimeError("v2 Python环境缺失，请运行准备程序")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen([str(python), "-m", "uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", str(port)], cwd=project, env=environment, stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
    (runtime / "server.pid.json").write_text(json.dumps({"pid": process.pid, "port": port, "project": str(project)}), encoding="utf-8")
    print(f"已启动v2进程 PID={process.pid}，地址：http://127.0.0.1:{port}")
    print("启动记录：runtime/server.log；手机使用本机局域网地址和同一端口。")


if __name__ == "__main__":
    main()
