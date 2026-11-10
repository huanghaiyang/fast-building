# 快速构建建筑平台 — MVP 实施方案

## 一、背景与目标

当前仓库 `d:\sgames\fast_building` 为空，需要从零搭建一个「快速构建建筑」的开发平台：

- 把建筑拆解为可复用模块（墙、楼板、屋顶、门窗、楼梯、阳台等），按规则重新组合，批量生成各式建筑。
- 使用本机 Blender 完成建模与导出（而非在浏览器里重建几何）。
- 支持多种 PBR 贴图（BaseColor / Normal / Roughness / Metallic / AO / Height）。
- 形态：**Web 平台 + 本机 Blender 无头后台**，浏览器内 3D 预览；兼顾游戏低模与写实可视化。

已核实环境：

| 项 | 结论 |
| --- | --- |
| Blender | `D:\blender\blender.exe`，5.2.2 LTS，内置 Python 3.13.13 |
| glTF 导出 | `5.2\scripts\addons_core\io_scene_gltf2` 存在且默认启用 |
| 系统 Python | 3.11.9（anaconda，用于后端 venv） |
| Node | v22.22.0 / npm 10.9.4 |
| 依赖落盘 | 遵循偏好：venv、npm cache 统一放 `D:\thirdparty`，不污染 C 盘 |

## 二、总体架构与目录

```
d:\sgames\fast_building\
├─ backend\                 FastAPI 服务（系统 Python 3.11 venv）
│  ├─ requirements.txt
│  └─ app\
│     ├─ main.py            应用装配、静态目录挂载
│     ├─ api\               health / modules / styles / texturesets / generate / jobs
│     ├─ services\          blender_runner.py、jobs.py、textures.py
│     └─ schemas.py         Pydantic 请求/响应模型
├─ generator\               仅在 Blender 内运行的 bpy 包（后端不导入）
│  ├─ entry.py              命令行入口：--job <job.json>，输出标记日志
│  ├─ schema.py             BuildingSpec / 模块描述符数据类与校验
│  ├─ geom\                 wall_panel.py、slab.py、roof.py、stair.py、opening.py、railing.py
│  ├─ assemble.py           footprint → BuildingSpec → bpy 场景
│  ├─ material\pbr.py       贴图集加载、材质构建、UV 规则
│  └─ exporter.py           GLB 导出、清理、统计
├─ frontend\                Vite + React + TS + three.js（R3F）
│  └─ src\{api, panels, viewer, store.ts, App.tsx}
├─ data\
│  ├─ modules\              模块描述符 JSON
│  ├─ styles\               风格预设（现代住宅 / 联排 / 办公 / 乡村）
│  ├─ texturesets\<name>\   PBR 通道图 + set.json
│  └─ jobs\<jobId>\         in.json、out\model.glb、out\meta.json、log.txt
├─ tools\                   pack_orm.py、validate_gltf.py、test_wall_panel.py
└─ .trae\documents\         方案文档
```

生成链路：浏览器提交参数 → 后端写入 `data\jobs\<id>\in.json` → 串行队列启动
`blender.exe -b --factory-startup --python-exit-code 1 --python generator\entry.py -- --job <abs path>`
→ 子进程 stdout 输出 `@@STAGE name 0.35` / `@@DONE <glb>` → 后端解析并更新任务表 → 前端轮询后加载 GLB。

关键约束：参数用 list 传递（不经过 shell）、jobId 与产物名全 ASCII、`PYTHONIOENCODING=utf-8`、Windows 下 `CREATE_NO_WINDOW`、每任务 `proc.wait(timeout=180)` 超时 kill。

## 三、模块与「拆解规范」

模块描述符 `data\modules\<id>.json` 字段：

```json
{
  "id": "wall_basic_a",
  "name": "基础外墙 A",
  "version": 1,
  "category": "wall | slab | roof | opening | stair | balcony",
  "units": "m",
  "tags": ["facade", "exterior"],
  "bbox": { "min": [0, 0, 0], "max": [4, 0.24, 3] },
  "geom": { "type": "wall_panel", "default_width": 4, "default_height": 3, "thickness": 0.24 },
  "sockets": [
    { "name": "end_left", "type": "wall_end", "pos": [0, 0, 0], "normal": [0, -1, 0], "width": 4, "angle": 90 }
  ],
  "slots": [
    { "name": "facade", "texset": "brick_red", "tile_m": 1.2 },
    { "name": "trim", "texset": "concrete_gray", "tile_m": 1.0 }
  ],
  "lod": [{ "level": 0, "ratio": 1.0 }],
  "source": { "blend": "", "collection": "MOD_wall_basic_a" }
}
```

自动拆分约定（MVP 只做约定化拆分，不做几何语义分析）：

- 集合命名 `MOD_<category>_<name>`；对象命名 `_L0/_L1` 归入同一模块的 LOD。
- 空物体命名 `SOCK_<type>_<name>`，本地 -Y 为法线、+Z 为上，导出为 socket。
- 对象自定义属性 `slot`、`tile_m` 决定材质槽与贴图密度。
- 导入时按集合切分、重置原点、复制到独立 `.blend`，并校验 UV 包围盒 ≈ 尺寸 / `tile_m`（偏差 >10% 告警）。

## 四、参数化组合算法

输入 footprint：

```json
{
  "width": 12, "depth": 9, "bays": 3, "floors": 3, "floor_height": 3.0,
  "roof": "flat | gable", "roof_pitch": 30,
  "style": "modern_villa", "textureset": "brick_red", "lod": 0, "seed": 42,
  "openings": { "window_w": 1.4, "window_h": 1.6, "sill_h": 0.9, "door_w": 1.0, "door_h": 2.1 }
}
```

1. `plan_bays(width, depth, bays)` → x/y 轴网；`plan_floors(floors, h)` → z 标高。
2. 每层每开间生成 4 段外墙；按风格预设决定门窗数量、宽高、间距，用 `seed` 做确定性抖动（可复现）。
3. 无布尔墙体：把墙面视为「矩形挖矩形洞」，用矩形分解生成前/后面与洞口侧壁，全部 `bmesh` 手工建面，`remove_doubles(1e-4)` + `recalc_face_normals`，并断言 `non_manifold == 0`。
4. 楼板 `slab()`（可留楼梯洞）、楼梯 `stair()`（直跑/双跑）、屋顶 `roof()`（平屋顶挑檐 / 双坡 + 山墙三角面，不用布尔）。
5. 模块按 socket 对齐到世界坐标，同 `texset` 共享材质，join 成 `BUILDING`，保留部件对象/顶点组用于统计。

`assemble.py` 只产出纯数据 `BuildingSpec`（可单测），`geom\` 与 `exporter.py` 才接触 `bpy`。

## 五、PBR 管线

- 贴图集目录：`data\texturesets\<name>\{basecolor,normal,roughness,metallic,ao,height}.png + set.json`，`set.json` 记录分辨率、`tile_m`、license、source。
- 上传后由后端规范化：统一转 PNG、边长取 2 的幂、仅 BaseColor 为 sRGB，其余 Non-Color；生成 `orm.png`（R=AO、G=Roughness、B=Metallic，glTF 约定）。`height` 不导出，仅存档。
- 必须自行打 ORM：Blender 5.2 导出器仅在 AO/Metallic/Roughness 源图尺寸一致时才合并，否则拆成多图导致体积翻倍；预打包后 Blender 端只做「一图三通道」。
- Blender 材质：`Image(orm, Non-Color) → Separate Color`，G→Roughness、B→Metallic、R→`glTF Material Output` 组的 Occlusion；法线走 Normal Map 节点。
- UV：`uv = 面所在平面坐标 / tile_m`，按真实米数取 UV，保证不同尺寸模块贴图密度一致，依赖 repeat 采样。
- 导出参数：`GLB`、`export_image_format='AUTO'`、`export_texcoords/normals/apply/yup/extras=True`、`export_materials='EXPORT'`。

## 六、API 契约

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 返回 Blender 路径与版本 |
| GET | `/api/modules` `/api/styles` `/api/texturesets` | 资源列表 |
| POST | `/api/texturesets` | multipart 上传贴图集 |
| POST | `/api/generate` | 提交 footprint，返回 `{jobId}` |
| GET | `/api/jobs/{id}` | `status/stage/progress/logs/result{glb,preview,stats}` |
| POST | `/api/jobs/{id}/cancel` | 取消运行中任务 |
| GET | `/api/jobs?limit=20` | 最近任务 |

静态挂载 `/out` → `data\jobs`，产物 `out\model.glb`、`out\meta.json`（参数回放）、`out\preview.png`（前端截图回传）。

## 七、前端

单页三栏：

- 左：模块库（分类 tab、卡片、缩略图）。
- 中：3D 预览（R3F Canvas + GLTFLoader + OrbitControls + 环境光/HDRI + 网格地面 + 阴影），可切换「仅贴图 / 完整 PBR」，显示三角面数、贴图数。
- 右：参数表单（尺寸、开间、层数、层高、屋顶、风格、贴图集、LOD、seed）、生成按钮、进度条与日志、下载 GLB。

任务轮询 500ms，`succeeded` 后自动加载 GLB。

## 八、实施里程碑

| 阶段 | 内容 | 验证 |
| --- | --- | --- |
| M0 | 目录骨架、venv（`D:\thirdparty\venvs\fastbuild`）、FastAPI 健康接口、Vite 工程 | `GET /api/health` 返回版本；`npm run dev` 打开页面 |
| M1 | Blender 桥与 job 机制，生成测试立方体 GLB | 命令行直跑出现 `@@DONE`；`out\model.glb` 存在并通过 `tools\validate_gltf.py` |
| M2 | 无布尔墙面板（洞口 3 组用例） | `tools\test_wall_panel.py` 断言非流形边为 0、bbox 正确 |
| M3 | 整栋组合（墙/楼板/楼梯/屋顶） | GLB bbox ≈ (width, depth, floors×floor_height)，统计三角面 |
| M4 | PBR 材质 + ORM + UV 密度 | GLB 仅 1 张 ORM，浏览器目视法线/粗糙度生效 |
| M5 | 前后端闭环（参数→生成→轮询→预览→下载） | 页面完成一次完整生成并可下载 |
| M6 | 批量与稳定性（20 栋随机） | 记录 P50/P95 耗时，失败可重试、超时被 kill |

## 九、风险与取舍

- **Blender API 漂移**：只用 `bmesh`、`mesh.from_pydata` 等稳定 API，不依赖 UI 上下文与渲染引擎。
- **导出耗时**：冷启 + 导出约 3–8s/栋，MVP 串行队列可接受；后续可换常驻 Blender 进程。
- **贴图体积/版权**：仅允许 PNG ≤2K，GLB 目标 <8MB，`set.json` 记录 license/source。
- **中文路径**：josId 与产物名全 ASCII，JSON 统一 UTF-8，子进程用绝对路径 + list 参数。
- **预览缩略图**：不在后台用 EEVEE 渲染（headless GPU 上下文风险高），改用前端 three.js 截图回传。

## 十、验收方式

1. 构建：`D:\blender\blender.exe -b --factory-startup --python generator\entry.py -- --job data\jobs\demo\in.json`，输出 GLB。
2. 服务：`python backend\run.py`，`GET /api/health`、`POST /api/generate`、轮询 `/api/jobs/{id}` 至 `succeeded`。
3. 前端：打开 5120，选风格 + 贴图集生成，预览出现带 PBR 贴图的建筑，可下载 GLB。
4. 质量断言：非流形边为 0、GLB 通过验证、贴图仅 1 张 ORM。
