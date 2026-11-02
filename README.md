# 多人协同应急处突模拟与评价软件 — 可运行原型

零依赖，仅需 Python 3。

## 运行
```bash
python server.py          # 默认 8080
python server.py 8099     # 指定端口
```
浏览器打开 http://127.0.0.1:8080

## 操作
1. 点「▶ 开始演练」——事件按 tick 演化（强度上升、半径扩散）
2. 右上角选「二维态势 / 三维等距」切换视图
3. 在「席位调度」选资源，点击画布目标格 → 下发调度指令，资源前往处置
4. 事件强度降到 0.25 或跑满 30 tick → 自动评分（时效/资源调度/流程合规/综合）
5. 拖动「回放」时间轴复现每一帧态势

## 模块对应（需求逐条命中）
- 方案采集：默认想定 `default_scenario()`，可 POST `/api/scenario` 自定义
- 突发事件构建：`step()` 事件引擎（蔓延/强度/资源调度）
- 多人协同练习：SSE 实时广播 `/api/stream`，多席位共享状态
- 回放评价：`timeline` 时序录制 + `evaluate()` 多维评分
- 二维三维态势：`index.html` Canvas 2D + 等距(Isometric)三维

## API
| 方法 | 路径 | 作用 |
|------|------|------|
| GET | /api/state | 当前态势 |
| GET | /api/stream | SSE 实时推送 |
| GET | /api/replay | 回放时间帧 |
| POST | /api/scenario | 设置想定 |
| POST | /api/start · /api/stop · /api/reset | 演练控制 |
| POST | /api/command | 席位下发调度指令 |

---

## 💝 赞助 / 打赏

如果这个项目对你有帮助，欢迎通过 **爱发电** 请我喝杯咖啡 ☕  
👉 https://afdian.com/a/Zhiyilang

> GitHub Sponsors 在中国大陆暂不支持个人账号，赞助统一走爱发电。

---
## 💝 赞助 / 支持
如果这个项目对你有帮助，欢迎到 [爱发电](https://afdian.com/a/Zhiyilang) 请我喝杯咖啡 ☕
你的支持是我持续维护开源、做更多实用工具的动力。

。
