"""Owned real MySQL/MongoDB processes with data and logs on V:. No service control."""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def binary(env_name, candidates):
    for candidate in [os.environ.get(env_name), shutil.which(env_name.removesuffix("_EXE").lower()), *candidates]:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    raise RuntimeError(f"BLOCKED: {env_name} executable unavailable; set {env_name}")


def v_directory(path):
    path = Path(path).resolve()
    if not Path("V:/").is_dir() or path.drive.upper() != "V:":
        raise RuntimeError("BLOCKED: V: is required for real database data/logs")
    path.mkdir(parents=True, exist_ok=True)
    return path


class MongoServer:
    def __init__(self, directory):
        self.directory = v_directory(directory)
        self.data = self.directory / "data"
        self.data.mkdir(exist_ok=True)
        self.exe = binary("MONGOD_EXE", ["C:/Program Files/MongoDB/Server/8.2/bin/mongod.exe"])
        self.port = free_port()
        self.uri = f"mongodb://127.0.0.1:{self.port}"
        self.process = None

    def start(self):
        from pymongo import MongoClient
        self.process = subprocess.Popen([str(self.exe), "--dbpath", str(self.data), "--port", str(self.port),
            "--bind_ip", "127.0.0.1", "--logpath", str(self.directory / "mongod.log"), "--logappend"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"MongoDB exited; inspect {self.directory / 'mongod.log'}")
            try:
                with MongoClient(self.uri, serverSelectionTimeoutMS=300) as client:
                    client.admin.command("ping")
                return self
            except Exception:
                time.sleep(.2)
        self.stop()
        raise RuntimeError("BLOCKED: disposable MongoDB did not become ready")

    def stop(self):
        if self.process and self.process.poll() is None:
            from pymongo import MongoClient
            try:
                with MongoClient(self.uri, serverSelectionTimeoutMS=500) as client:
                    client.admin.command("shutdown", force=True)
            except Exception:
                pass
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.terminate()  # only the Popen process created by this object
                self.process.wait(timeout=10)


class MysqlServer:
    def __init__(self, directory):
        self.directory = v_directory(directory)
        self.data = self.directory / "data"
        self.exe = binary("MYSQLD_EXE", ["C:/Program Files/MySQL/MySQL Server 8.0/bin/mysqld.exe"])
        self.port = free_port()
        self.process = None

    def start(self):
        import mysql.connector
        if self.data.exists():
            raise RuntimeError(f"Refusing existing MySQL data directory {self.data}")
        base = [str(self.exe), "--no-defaults", f"--basedir={self.exe.parent.parent}", f"--datadir={self.data}"]
        log = self.directory / "mysql.log"
        with log.open("w") as output:
            subprocess.run([*base, "--initialize-insecure", "--console"], stdout=output,
                           stderr=subprocess.STDOUT, check=True, timeout=60)
        self.process = subprocess.Popen([*base, f"--port={self.port}", "--bind-address=127.0.0.1", "--mysqlx=OFF",
            "--log-bin-trust-function-creators=1", f"--log-error={log}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"MySQL exited; inspect {log}")
            try:
                cnx = mysql.connector.connect(host="127.0.0.1", port=self.port, user="root", password="", connection_timeout=1)
                cnx.close()
                return self
            except mysql.connector.Error:
                time.sleep(.2)
        self.stop()
        raise RuntimeError("BLOCKED: disposable MySQL did not become ready")

    def stop(self):
        if self.process and self.process.poll() is None:
            import mysql.connector
            try:
                cnx = mysql.connector.connect(host="127.0.0.1", port=self.port, user="root", password="")
                cnx.cmd_shutdown()
                cnx.close()
            except mysql.connector.Error:
                pass
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=10)
