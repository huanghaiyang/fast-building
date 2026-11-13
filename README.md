# Fast Building · 快速构建建筑平台

本机 **Blender 无头建模 + Web 工作台** 的模块化建筑生成平台：

- 从模块库（墙体 / 楼板 / 屋顶 / 门窗 / 楼梯 / 阳台 / 基座 / 门廊…）与参数化规则组装整栋建筑；
- 由本机 Blender 在后台无头生成 **GLB（含 PBR 贴图）**，浏览器里用 three.js 预览、实时编辑、下载；
- 提供模块缩略图与三维预览缓存（后台预热），支持中世纪 / 乡土 / 废墟 / 街市等风格化构件开关。

技术栈：FastAPI + Uvicorn（后端）、React 18 + Vite 5 + three.js（前端）、Blender Python（生成器）。

---

## 环境要求

| 依赖 | 版本 / 默认路径 | 说明 |
| --- | --- | --- |
| Windows | 10/11 | 脚本与部分路径按 Windows 编写，核心代码跨平台 |
| Node.js | ≥ 18.20 | 需全局 `fetch`、`AbortSignal.timeout` |
| Python | 3.11，默认 `D:\thirdparty\venvs\fastbuild` | 可用 `FASTBUILD_PYTHON` 覆盖 |
| Blender | 4.x / 5.x，默认 `D:\blender\blender.exe` | 需支持 `blender -b --python` 无头运行，可用 `FB_BLENDER_EXE` 覆盖 |

## 安装

```bash
# 前端依赖（node_modules 不入库，首次必须安装）
cd frontend
npm install
cd ..

# 后端依赖（建议使用项目 venv）
python -m pip install -r backend/requirements.txt
```

## 启动

```bash
npm start          # 等价 npm run dev：前后端一起启动，带热更新
```

启动后：

- 前端（Vite HMR）：<http://127.0.0.1:5120>
- 后端（API 文档）：<http://127.0.0.1:8756/docs> ，健康检查 <http://127.0.0.1:8756/api/health>
- 前端把 `/api`、`/out`、`/tex` 反向代理到后端 8756，页面内无需关心跨端口

前后端在**前台**运行，日志带 `[api]` / `[web]` 前缀；按 **Ctrl+C** 会整树结束前后端，不留孤儿进程（因此不再需要单独的 stop / restart 脚本）。

## 常用命令

| 命令 | 作用 |
| --- | --- |
| `npm start` / `npm run dev` | 开发模式：后端 `uvicorn --reload` + 前端 Vite HMR |
| `npm run prod` | 生产模式：重新构建前端，由后端单端口 8756 托管（无热更新） |
| `npm run api` | 只启动后端（`uvicorn --reload`） |
| `npm run web` | 只启动前端（Vite HMR） |
| `npm run build` | 只构建前端到 `frontend/dist` |
| `npm run typecheck` | 前端 TypeScript 类型检查 |

所有命令都由 [scripts/dev.mjs](scripts/dev.mjs) 编排：解析参数 → 检查端口占用 → 启动子进程 → 等待就绪 → 打印访问地址。端口被占用时会直接打印占用 PID 并退出，避免连到旧实例。

等价的原始调用方式：`node scripts/dev.mjs --prod` / `--only api` / `--only web` / `--build`。

## 热更新说明

- **后端**：`python backend/run.py --reload` 监听 `backend/` 与 `generator/` 下的 `.py`，保存即重启。
  - 不监听 `data/`：任务产物与预览缓存持续写入，监听会导致反复重启；
  - Windows 下修补了 uvicorn 原生 reload 的「重启卡死」问题（原生实现依赖控制台 `CTRL_C_EVENT`，在无控制台/输出重定向场景下收不到事件，会永久阻塞在 `process.join()`）。现改为 `Process.terminate()` 重启，并复位内部标记，保证第一次 Ctrl+C 就能退出。
- **前端**：Vite HMR / React Fast Refresh，改 `frontend/src` 即时生效；`vite.config.ts` 固定 `127.0.0.1:5120` + `strictPort`，不会悄悄换端口。
- **构建**：`vite build` 时把 `TMP/TEMP` 指向 `frontend/node_modules/.tmp`，规避系统临时目录不可写/不可删导致的 esbuild `Access is denied`。

## 目录结构

```
backend/            FastAPI 服务
  app/main.py       应用入口（挂载 /api、/out、/tex，dist 存在时托管前端）
  app/api/          资源与任务接口
  app/services/     任务队列、模块预览预热、贴图集
  run.py            启动入口（--reload / --host / --port）
frontend/           React 18 + Vite 5 + three.js
  src/panels/       模块库、参数面板、工作室面板
  src/viewer/       建筑预览、特效、程序化与细分逻辑
  vite.config.ts    端口 / 严格端口 / 反向代理
generator/          Blender 生成器（entry.py 为入口；assemble/schema/exporter/preview…）
data/               modules / styles / texturesets / previews / jobs / hdr
tools/              校验与批测脚本（validate_gltf、batch_test、qa_styles、render_style…）
scripts/dev.mjs     npm 编排入口（前后端启动 / 构建 / 只起单端）
.run/               本地临时产物（已 git 忽略）
```

## 配置（环境变量）

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `FASTBUILD_PYTHON` | `D:\thirdparty\venvs\fastbuild\Scripts\python.exe` | Python 解释器（`scripts/dev.mjs` 优先读取） |
| `FB_BLENDER_EXE` | `D:\blender\blender.exe` | Blender 可执行文件 |
| `FB_HOST` / `FB_PORT` | `127.0.0.1` / `8756` | 后端监听地址与端口 |
| `FB_JOB_TIMEOUT` | `180` | 单个生成任务超时（秒） |

端口约定：后端 **8756**、前端 **5120**。若修改端口，需同步更新 `frontend/vite.config.ts` 的代理与 `backend/app/main.py` 的 CORS 白名单。

## API 一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 服务与 Blender 可用状态 |
| GET | `/api/modules` | 模块库列表 |
| GET | `/api/modules/{id}/preview.glb` | 模块三维预览（首次访问由 Blender 生成并缓存） |
| GET | `/api/modules/{id}/thumbnail.png` | 模块缩略图（同上，后台预热） |
| GET | `/api/styles` | 风格预设 |
| GET / POST | `/api/texturesets` | 贴图集列表 / 上传 |
| POST | `/api/generate` | 提交生成任务，返回 `{ job_id }` |
| GET | `/api/jobs?limit=20` | 最近任务 |
| GET | `/api/jobs/{id}` | 任务状态、阶段、进度、日志、结果 |
| POST | `/api/jobs/{id}/cancel` | 取消运行中的任务 |
| GET | `/docs` | Swagger 文档 |

生成请求示例（字段与 `generator/schema.py` 的 `BuildingSpec` 对应）：

```json
{
  "width": 12,
  "depth": 9,
  "bays": 3,
  "floors": 3,
  "floor_height": 3.0,
  "roof": "gable",
  "roof_pitch": 30,
  "style": "modern_villa",
  "textureset": "brick_red",
  "seed": 42,
  "balcony": true,
  "smooth": true,
  "subdiv": 1,
  "medieval": { "timber_frame": true, "jetty": true }
}
```

轮询 `GET /api/jobs/{id}` 至 `status=succeeded`，通过 `result.glb`（形如 `/out/<job>/out/model.glb`）加载模型，`result.meta` 为参数回放，`result.stats` 为统计信息。

## 数据与产物

- `data/modules`、`data/styles`、`data/texturesets`：模块、风格、贴图集描述（入库）；
- `data/previews`：模块 GLB/PNG 缓存（入库，随 generator / 模块描述变更自动重建）；
- `data/jobs`：任务输入与产物，由 `/out` 静态挂载（**不入库**）；
- `data/hdr`：环境贴图目录（当前为空，前端使用程序化天空，不依赖外部 HDR）；
- `frontend/dist`：前端构建产物（**不入库**）。

## 常见问题

- **端口被占用**：启动时会打印占用端口的 PID；先结束该进程，或同时修改后端端口与前端代理/CORS。
- **找不到 Python**：设置 `FASTBUILD_PYTHON` 指向可用的 `python.exe`。
- **`/api/health` 返回 `blender.ok=false`**：检查 `FB_BLENDER_EXE` 与 Blender 是否可无头运行。
- **首次启动或改过 `generator/` 后较慢**：模块缩略图/预览会由 Blender 重新生成（后台预热按需补齐），属正常现象。
- **前端页面空白**：确认 `frontend/node_modules` 已安装、5120 端口无旧实例占用。
- **`vite build` 报 `Access is denied`**：已内置 `TMP/TEMP` 重定向；若仍出现，清理 `frontend/node_modules/.tmp` 后重试。
