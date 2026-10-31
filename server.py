#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多人协同应急处突模拟与评价软件 — 可运行原型 (MVP)
红山·软件快响 任务三 阶段一 / 阶段二交付物

零依赖：仅 Python 3 标准库。
启动:  python server.py  →  http://127.0.0.1:8080
功能: 方案采集 / 事件构建 / 多人协同(席位) / 回放 / 二维三维态势 / 自动评价
"""
import json, threading, time, random
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

GRID = 20
state = {
    "running": False,
    "tick": 0,
    "scenario": None,
    "event": None,          # {"x":, "y":, "level":, "radius":, "intensity":}
    "resources": [],        # [{"id","type","x","y","target":None,"busy":False}]
    "roles": [],            # 席位: 指挥/消防/医疗/舆情/交通
    "log": [],              # 处置日志
    "timeline": [],         # 回放序列
    "scores": None,
}
lock = threading.Lock()
LISTENERS = []  # SSE clients
T0 = time.time()


# ---------- 仿真引擎 ----------
def default_scenario():
    return {
        "name": "城市综合体火灾想定",
        "grid": GRID,
        "event": {"x": 10, "y": 10, "level": 3, "radius": 2, "intensity": 1.0},
        "resources": [
            {"id": "F1", "type": "fire", "x": 3, "y": 3},
            {"id": "F2", "type": "fire", "x": 16, "y": 4},
            {"id": "M1", "type": "medical", "x": 4, "y": 16},
            {"id": "P1", "type": "police", "x": 17, "y": 17},
        ],
        "roles": ["指挥", "消防", "医疗", "舆情", "交通"],
    }


def reset(scn=None):
    global state
    scn = scn or default_scenario()
    with lock:
        state["running"] = False
        state["tick"] = 0
        state["scenario"] = scn
        state["event"] = dict(scn["event"])
        state["resources"] = [dict(r) for r in scn["resources"]]
        for r in state["resources"]:
            r["target"] = None
            r["busy"] = False
        state["roles"] = list(scn["roles"])
        state["log"] = []
        state["timeline"] = []
        state["scores"] = None


def step():
    with lock:
        s = state
        s["tick"] += 1
        ev = s["event"]
        # 事件蔓延：强度随时间略增，半径微扩
        ev["intensity"] = min(2.0, ev["intensity"] + 0.02)
        ev["radius"] = min(GRID // 2, ev["radius"] + (0.05 if ev["intensity"] > 1.3 else 0))
        # 资源向目标移动 / 抵达后灭火
        contained = 0
        for r in s["resources"]:
            if r["target"]:
                tx, ty = r["target"]
                dx, dy = tx - r["x"], ty - r["y"]
                stepx = 1 if dx > 0 else (-1 if dx < 0 else 0)
                stepy = 1 if dy > 0 else (-1 if dy < 0 else 0)
                r["x"] += stepx
                r["y"] += stepy
                if r["x"] == tx and r["y"] == ty:
                    r["busy"] = True
                    r["target"] = None
                    # 灭火效果：靠近事件则降低强度
                    if abs(r["x"] - ev["x"]) <= ev["radius"] and abs(r["y"] - ev["y"]) <= ev["radius"]:
                        ev["intensity"] = max(0.2, ev["intensity"] - 0.15)
                        contained += 1
            else:
                # 自动趋近事件（无人指挥时的最低自动行为）
                if abs(r["x"] - ev["x"]) > ev["radius"] or abs(r["y"] - ev["y"]) > ev["radius"]:
                    r["target"] = (ev["x"], ev["y"])
        # 记录时间帧
        s["timeline"].append({
            "tick": s["tick"],
            "event": dict(ev),
            "resources": [{"id": r["id"], "x": r["x"], "y": r["y"], "busy": r["busy"]} for r in s["resources"]],
        })
        # 处置日志（示例触发）
        if s["tick"] % 5 == 0:
            s["log"].append({"t": s["tick"], "msg": f"事件强度 {ev['intensity']:.2f}，已调度 {contained} 单位抵近"})
        # 自动评价
        if s["tick"] >= 30 or ev["intensity"] <= 0.25:
            s["running"] = False
            evaluate()


def evaluate():
    with lock:
        s = state
        ev = s["event"]
        # 时效：事件被压制到 0.25 以下所用 tick
        timeliness = max(0, 100 - s["tick"] * 2)
        # 资源调度：平均抵近率
        arrived = sum(1 for r in s["resources"] if r["busy"])
        dispatch = int(arrived / max(1, len(s["resources"]) / 2) * 100)
        # 流程合规：是否触发过日志处置
        compliance = 100 if s["log"] else 0
        total = int((timeliness * 0.4 + min(100, dispatch) * 0.4 + compliance * 0.2))
        s["scores"] = {
            "时效": timeliness, "资源调度": min(100, dispatch),
            "流程合规": compliance, "综合": total,
            "ticks_used": s["tick"], "final_intensity": round(ev["intensity"], 2),
        }


def loop():
    while True:
        time.sleep(1)
        with lock:
            run = state["running"]
        if run:
            step()
            broadcast()


# ---------- SSE ----------
def broadcast():
    with lock:
        payload = "data: " + json.dumps(snapshot()) + "\n\n"
        dead = []
        for q in LISTENERS:
            try:
                q.put(payload)
            except Exception:
                dead.append(q)
        for q in dead:
            LISTENERS.remove(q)


def snapshot():
    with lock:
        return {
            "tick": state["tick"], "running": state["running"],
            "event": state["event"], "resources": state["resources"],
            "roles": state["roles"], "log": state["log"][-8:],
            "scores": state["scores"],
            "timeline_len": len(state["timeline"]),
        }


# ---------- HTTP ----------
class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
        self.wfile.write(body.encode("utf-8"))

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            try:
                with open("index.html", "r", encoding="utf-8") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            except FileNotFoundError:
                self._send(404, "index.html missing")
        elif u.path == "/api/state":
            self._send(200, snapshot())
        elif u.path == "/api/replay":
            with lock:
                self._send(200, {"timeline": state["timeline"]})
        elif u.path == "/api/stream":
            self._sse()
        else:
            self._send(404, {"err": "not found"})

    def _sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        import queue
        q = queue.Queue()
        LISTENERS.append(q)
        try:
            self.wfile.write(("data: " + json.dumps(snapshot()) + "\n\n").encode("utf-8"))
            while True:
                msg = q.get(timeout=30)
                self.wfile.write(msg.encode("utf-8"))
                self.wfile.flush()
        except Exception:
            if q in LISTENERS:
                LISTENERS.remove(q)

    def do_POST(self):
        u = urlparse(self.path)
        try:
            ln = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(ln) if ln else b"{}"
            data = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            data = {}
        if u.path == "/api/scenario":
            reset(data.get("scenario"))
            broadcast()
            self._send(200, snapshot())
        elif u.path == "/api/start":
            with lock:
                if state["scenario"] is None:
                    reset()
                state["running"] = True
            broadcast()
            self._send(200, {"ok": True, "running": True})
        elif u.path == "/api/stop":
            with lock:
                state["running"] = False
            evaluate()
            broadcast()
            self._send(200, snapshot())
        elif u.path == "/api/command":
            # 席位下发指令：调度某资源至坐标
            rid = data.get("resource")
            x, y = data.get("x", 0), data.get("y", 0)
            with lock:
                for r in state["resources"]:
                    if r["id"] == rid:
                        r["target"] = (x, y)
                        r["busy"] = False
                        state["log"].append({"t": state["tick"], "msg": f"席位指令：{rid} → ({x},{y})"})
            broadcast()
            self._send(200, {"ok": True})
        elif u.path == "/api/reset":
            reset()
            broadcast()
            self._send(200, snapshot())
        else:
            self._send(404, {"err": "not found"})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    import sys
    PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    reset()
    threading.Thread(target=loop, daemon=True).start()
    print(f"应急处突模拟原型 → http://127.0.0.1:{PORT}  (Ctrl+C 退出)")
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
