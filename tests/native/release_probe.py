"""真实 SDK 只连接本机假 TCP 前置，复现退出与 Python 回调争用 GIL。"""

import queue
import socket
import sys
import tempfile
import threading
import time

from vnpy_ctp import TdApi


def run(scenario: str) -> None:
    accepted: queue.Queue[socket.socket | BaseException] = queue.Queue()
    entered = threading.Event()
    returned = threading.Event()

    class Probe(TdApi):
        def onFrontDisconnected(self, reason):
            entered.set()
            if scenario == "callback_in_progress":
                time.sleep(0.2)
            returned.set()

    with socket.socket() as listener, tempfile.TemporaryDirectory() as path:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        listener.settimeout(10)

        def accept():
            try:
                connection, _ = listener.accept()
                connection.settimeout(10)
                connection.recv(4096)
                accepted.put(connection)
            except BaseException as error:
                accepted.put(error)

        server = threading.Thread(target=accept, daemon=True)
        server.start()
        api = Probe()
        api.createFtdcTraderApi(path + "/", True)
        api.registerFront(f"tcp://127.0.0.1:{listener.getsockname()[1]}")
        api.subscribePrivateTopic(2)
        api.subscribePublicTopic(2)
        api.init()
        connection = accepted.get(timeout=12)
        if isinstance(connection, BaseException):
            api.exit()
            raise connection
        server.join(timeout=1)
        interval = sys.getswitchinterval()
        try:
            if scenario == "callback_waiting_for_gil":
                sys.setswitchinterval(10)
                connection.close()
                deadline = time.monotonic() + 0.2
                while time.monotonic() < deadline:
                    pass
            elif scenario == "callback_in_progress":
                connection.close()
                assert entered.wait(10), "真实断线回调没有到达"
            else:
                raise ValueError(scenario)
            api.exit()
            if scenario == "callback_in_progress":
                assert returned.is_set(), "退出必须等待已进入的回调完成"
        finally:
            sys.setswitchinterval(interval)
            connection.close()
    print("released", flush=True)


if __name__ == "__main__":
    run(sys.argv[1])
