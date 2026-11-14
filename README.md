# Fast Building · 快速构建建筑平台

本机 **Blender 无头建模 + Web 工作台** 的模块化建筑生成平台：

- 从模块库（墙体 / 楼板 / 屋顶 / 门窗 / 楼梯 / 阳台 / 基座 / 门廊…）与参数化规则组装整栋建筑；
- 由本机 Blender 在后台无头生成 **GLB（含 PBR 贴图）**，浏览器里用 three.js 预览、实时编辑、下载；
- 提供模块缩略图与三维预览缓存（后台预热），支持中世纪 / 乡土 / 废墟 / 街市等风格化构件开关；
- **可开合门窗**：门扇 / 窗扇是独立节点，点击即可开关，也可一键全开 / 全关；全部只向室外开，宽窗为左右对开双扇；
- **水磨坊**：水轮持续转动，轮坑水面为动态水体着色器（波纹 / 高光 / 泡沫）；
- **雪景**：逐粒大小/透明度的软粒子降雪 + 按坡向与噪声分布的屋面积雪，可手动控制覆盖度；
- **真实昼夜循环**：太阳东升西落，主光强度/色温、天空渐变、雾、环境光与星点随时间变化。

技术栈：FastAPI + Uvicorn（后端）、React 18 + Vite 5 + three.js（前端）、Blender Python（生成器）。

---

## 环境要求

| 依赖 | 版本 / 默认路径 | 说明 |
| --- | --- | --- |
| Windows | 10/11 | 脚本与部分路径按 Windows 编写，核心代码跨平台 |
| Node.js | ≥ 18.20 | 需全局 `fetch`、`AbortSignal.timeout` |
| Python | 3.11，默认 `D:\thirdparty\venvs\fastbuild` | 可在 `.env` 用 `FASTBUILD_PYTHON` 覆盖 |
| Blender | 4.x / 5.x，默认 `D:\blender\blender.exe` | 需支持 `blender -b --python` 无头运行，可在 `.env` 用 `FB_BLENDER_EXE` 覆盖 |

## 配置（.env）

可执行文件与端口统一在**项目根目录的 `.env`** 中配置（模板见 [.env.example](.env.example)，`.env` 已被 git 忽略）：

```ini
FASTBUILD_PYTHON=D:\thirdparty\venvs\fastbuild\Scripts\python.exe
FB_BLENDER_EXE=D:\blender\blender.exe
FB_HOST=127.0.0.1
FB_PORT=8756
FB_FRONTEND_HOST=127.0.0.1
FB_FRONTEND_PORT=5120
FB_JOB_TIMEOUT=180
```

这份配置同时被三处读取：`scripts/dev.mjs`（启动编排）、`backend/app/env.py`（Python 侧）、`frontend/vite.config.ts`（dev server 与代理）。**真实环境变量优先于 `.env`**，便于 CI 或多机覆盖。

## 安装

```bash
# 前端依赖（node_modules 不入库，首次必须安装）
cd frontend
npm install
cd ..

# 后端依赖（建议使用项目 venv 的 python）
python -m pip install -r backend/requirements.txt
```

## 启动

```bash
npm start          # 等价 npm run dev：前后端一起启动，带热更新
```

启动后：

- 前端（Vite HMR）：<http://127.0.0.1:5120>
- 后端（API 文档）：<http://127.0.0.1:8756/docs> ，健康检查 <http://127.0.0.1:8756/api/health>
- 前端把 `/api`、`/out`、`/tex` 反向代理到后端（地址取自 `.env`），页面内无需关心跨端口

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
- **前端**：Vite HMR / React Fast Refresh，改 `frontend/src` 即时生效；`vite.config.ts` 的 host/port 取自 `.env`，`strictPort` 保证端口被占用时明确失败。
- **模块预览**：generator 或缩略图逻辑变化后，后端预热检测到时间戳变化会自动重建；也可用 `tools/rebuild_module_previews.py` 一次性批量重建（见下文）。
- **构建**：`vite build` 时把 `TMP/TEMP` 指向 `frontend/node_modules/.tmp`，规避系统临时目录不可写/不可删导致的 esbuild `Access is denied`。

## 交互与特效（工作室 → 环境与特效）

- **门窗开合**：直接点击画面中的门扇 / 窗扇单独开关；面板里的「门窗全开 / 全关」批量控制。
- **开向规则**：门扇与窗扇一律**向室外**打开（按各朝向墙面实际法线计算，不会往室内开）；宽窗（≥0.98 m）为左右**对开双扇**、合起来是田字四格，窄窗为单扇竖梃——不存在「田字窗只从一侧掀开」。
- **默认表面水膜**：不需要先开雨，材质默认带一层薄水膜高光与顺墙细流痕；「降雨」面板里的湿度/流痕可继续加强。
- **水轮与水面**：水磨坊建筑的水轮持续自转，轮坑水面使用动态水体着色器（滚动波纹、菲涅耳、太阳高光、顺流泡沫），可在面板里关闭转动。
- **雪景**：`降雪强度` 控制雪粒密度；开启「自动积雪」后，朝上的屋面与地面会逐渐积累雪层，停雪后缓慢融化；也可直接拖动「积雪覆盖」。
- **昼夜循环**：开启后太阳按一天 24 小时东升西落，主光强度/色温、天空渐变、雾、环境光与夜空星点同步变化；`时间推进` 控制循环速度（小时/秒），`当前时间` 可直接跳到任意时刻。
- 雨天、体积光、剖切、体素碎裂等既有特效仍在同一面板。

## 即时预览与建模速度

生成参数面板底部有「**即时预览（纯前端体量）**」开关：勾选后拖动宽度/进深/开间/层数/屋顶等参数，前端会直接用 three.js 拼出体量、楼板、门窗示意与屋顶（毫秒级、带 120 ms 防抖），完全不需要等 Blender。

它只做体量/比例示意，不替代正式模型：点「生成建筑」仍由本机 Blender 生成带 PBR 贴图、木构细节、可开合门窗与水车的完整 GLB（单栋约 1 秒）。这样"调形"在前端即时完成，"出细节"再交给 Blender，是当前兼顾速度与质量的折中方案。

## 中世纪街市构件与互斥规则

「生成参数 → 中世纪街市」新增：**石板瓦曲面屋顶、磨坊水车、街市橱窗、门楣横招牌、马厩拱形开间、谷仓大门、挑楼托木、街市杂物、靠墙木梯**（此前水车等只有数据字段、没有勾选入口）。

面板会按互斥规则自动取消并置灰冲突项：

- 厚茅草屋顶 ⇄ 石板瓦曲面屋顶（且都只在双坡屋顶可用）；
- 木筋墙 ⇄ 圆木叠砌墙；尖拱门窗 ⇄ 半圆拱券；
- 街市橱窗 / 马厩开间 / 谷仓大门 三者互斥；
- 瞭望棚会替换整栋屋顶，自动清空老虎窗/垛口/钟塔/破损屋顶等；
- 整栋塌毁时，其余依赖正常墙身与屋顶的构件全部置灰并清空。

## 重新生成模块预览

调整了 `generator/preview.py` / `generator/thumbnail.py`（造型、取景、材质或缩略图风格）后，可一次性重建全部历史模块的 GLB 与缩略图（Blender 无头，约 20 秒）：

```bash
D:\blender\blender.exe -b --factory-startup --python tools/rebuild_module_previews.py
```

## 目录结构

```
backend/            FastAPI 服务
  app/main.py       应用入口（挂载 /api、/out、/tex，dist 存在时托管前端）
  app/env.py        读取项目根目录 .env（无第三方依赖）
  app/api/          资源与任务接口
  app/services/     任务队列、模块预览预热、贴图集
  run.py            启动入口（--reload / --host / --port）
frontend/           React 18 + Vite 5 + three.js
  src/panels/       模块库、参数面板、工作室面板
  src/viewer/       预览器、特效（雨/雪/体积光）、水面着色器、程序化材质、细分
  vite.config.ts    dev server 与代理（地址取自 .env）
generator/          Blender 生成器（entry.py 入口；assemble/schema/exporter/preview…）
  geom/openings.py  可开合的门扇 / 窗扇几何（原点在合页边）
data/               modules / styles / texturesets / previews / jobs / hdr
tools/              校验、批测与预览重建（validate_gltf、batch_test、qa_styles、rebuild_module_previews…）
scripts/dev.mjs     npm 编排入口（前后端启动 / 构建 / 只起单端）
.env                本地配置（已 git 忽略，模板见 .env.example）
.run/               本地临时产物（已 git 忽略）
```

## 配置（.env / 环境变量）

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `FASTBUILD_PYTHON` | `D:\thirdparty\venvs\fastbuild\Scripts\python.exe` | Python 解释器 |
| `FB_BLENDER_EXE` | `D:\blender\blender.exe` | Blender 可执行文件 |
| `FB_HOST` / `FB_PORT` | `127.0.0.1` / `8756` | 后端监听地址与端口 |
| `FB_FRONTEND_HOST` / `FB_FRONTEND_PORT` | `127.0.0.1` / `5120` | 前端 dev server 地址与端口（CORS / 代理自动跟随） |
| `FB_JOB_TIMEOUT` | `180` | 单个生成任务超时（秒） |

以上配置都写在项目根目录 `.env` 中；真实环境变量优先级更高。修改端口后无需再手动同步 Vite 代理或 CORS。

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

- **端口被占用**：启动时会打印占用端口的 PID；先结束该进程，或修改 `.env` 里的 `FB_PORT` / `FB_FRONTEND_PORT`（代理与 CORS 会自动跟随）。
- **找不到 Python**：在 `.env` 里把 `FASTBUILD_PYTHON` 指向可用的 `python.exe`（或改用系统环境变量覆盖）。
- **`/api/health` 返回 `blender.ok=false`**：检查 `.env` 的 `FB_BLENDER_EXE` 与 Blender 是否可无头运行。
- **首次启动或改过 `generator/` 后较慢**：模块缩略图/预览会由 Blender 重新生成（后台预热按需补齐），属正常现象；也可用 `tools/rebuild_module_previews.py` 主动重建。
- **前端页面空白**：确认 `frontend/node_modules` 已安装、`.env` 里前端端口未被旧实例占用。
- **`vite build` 报 `Access is denied`**：已内置 `TMP/TEMP` 重定向；若仍出现，清理 `frontend/node_modules/.tmp` 后重试。
- **门窗点不动 / 水轮不转**：这类交互依赖生成器写入的节点信息（`fb_kind` extras、`water_wheel` 节点名），需用当前版本的生成器重新生成模型（旧 GLB 不带这些信息）。
