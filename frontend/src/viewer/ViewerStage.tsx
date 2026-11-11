import { useEffect, useRef, useState } from "react";
import {
  BuildingViewer,
  ENVIRONMENTS,
  EnvironmentPreset,
  NodeInfo,
  SHADOW_QUALITIES,
  ShadowQuality,
  VIEW_AXES,
  ViewerStats,
  ViewerStatus,
} from "./BuildingViewer";
import { StudioPanel } from "../panels/StudioPanel";

interface Props {
  url: string | null;
}

/** 3D 预览舞台：包含画布、视角与环境工具条、模型统计浮层。 */
export function ViewerStage({ url }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<BuildingViewer | null>(null);
  const [viewer, setViewer] = useState<BuildingViewer | null>(null);
  const [studioOpen, setStudioOpen] = useState(false);
  const [nodeList, setNodeList] = useState<NodeInfo[]>([]);
  const [selectedNode, setSelectedNode] = useState<NodeInfo | null>(null);
  const [status, setStatus] = useState<ViewerStatus>("idle");
  const [message, setMessage] = useState<string>("");
  const [stats, setStats] = useState<ViewerStats | null>(null);
  const [autoRotate, setAutoRotate] = useState(false);
  const [wireframe, setWireframe] = useState(false);
  const [locked, setLocked] = useState(false);
  const [environment, setEnvironment] = useState<EnvironmentPreset>("midday");
  const [ambient, setAmbient] = useState(1);
  const [subdivision, setSubdivision] = useState(0);
  const [shadows, setShadows] = useState(true);
  const [shadowQuality, setShadowQuality] = useState<ShadowQuality>("medium");

  useEffect(() => {
    if (!hostRef.current) return;
    const instance = new BuildingViewer(hostRef.current);
    instance.onNodePick = (node) => setSelectedNode(node);
    viewerRef.current = instance;
    setViewer(instance);
    return () => {
      instance.onNodePick = null;
      instance.dispose();
      viewerRef.current = null;
      setViewer(null);
    };
  }, []);

  useEffect(() => {
    if (!url || !viewerRef.current) return;
    viewerRef.current.load(
      url,
      (next) => setStats(next),
      (next, msg) => {
        setStatus(next);
        setMessage(msg ?? "");
        if (next === "ready") {
          setNodeList(viewerRef.current?.getNodes() ?? []);
        }
      },
    );
  }, [url]);

  useEffect(() => {
    viewerRef.current?.setAutoRotate(autoRotate && !locked);
  }, [autoRotate, locked]);

  useEffect(() => {
    viewerRef.current?.setWireframe(wireframe);
  }, [wireframe]);

  useEffect(() => {
    viewerRef.current?.setEnvironment(environment);
  }, [environment]);

  useEffect(() => {
    viewerRef.current?.setLocked(locked);
  }, [locked]);

  useEffect(() => {
    viewerRef.current?.setAmbient(ambient);
  }, [ambient]);

  useEffect(() => {
    viewerRef.current?.setSubdivision(subdivision);
  }, [subdivision]);

  useEffect(() => {
    viewerRef.current?.setShadows(shadows, shadowQuality);
  }, [shadows, shadowQuality]);

  return (
    <section className="stage">
      <div className="stage-canvas" ref={hostRef} />

      <div className="stage-toolbar">
        <div className="toolbar-row">
          <span className="toolbar-label">视角</span>
          {VIEW_AXES.map((axis) => (
            <button
              key={axis.id}
              type="button"
              className="chip-btn"
              onClick={() => viewerRef.current?.setView(axis.id)}
            >
              {axis.label}
            </button>
          ))}
          <button
            type="button"
            className={`chip-btn ${locked ? "active" : ""}`}
            onClick={() => setLocked((value) => !value)}
          >
            {locked ? "已锁定" : "锁定视角"}
          </button>
        </div>

        <div className="toolbar-row">
          <span className="toolbar-label">环境</span>
          <select
            className="chip-select"
            value={environment}
            onChange={(event) => setEnvironment(event.target.value as EnvironmentPreset)}
          >
            {ENVIRONMENTS.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            className={`chip-btn ${autoRotate ? "active" : ""}`}
            disabled={locked}
            onClick={() => setAutoRotate((value) => !value)}
          >
            自动旋转
          </button>
          <button
            type="button"
            className={`chip-btn ${wireframe ? "active" : ""}`}
            onClick={() => setWireframe((value) => !value)}
          >
            线框
          </button>
          <button type="button" className="chip-btn" onClick={() => viewerRef.current?.resetView()}>
            重置视角
          </button>
          <button
            type="button"
            className={`chip-btn ${studioOpen ? "active" : ""}`}
            onClick={() => setStudioOpen((value) => !value)}
          >
            实时编辑
          </button>
        </div>

        <div className="toolbar-row">
          <span className="toolbar-label">环境光</span>
          <input
            className="chip-range"
            type="range"
            min={0}
            max={2}
            step={0.05}
            value={ambient}
            onChange={(event) => setAmbient(Number(event.target.value))}
          />
          <span className="chip-value">{ambient.toFixed(2)}</span>

          <span className="toolbar-label">细分</span>
          <select
            className="chip-select"
            title="曲面细分仅影响预览，不改变导出模型"
            value={subdivision}
            onChange={(event) => setSubdivision(Number(event.target.value))}
          >
            <option value={0}>关</option>
            <option value={1}>1 级</option>
            <option value={2}>2 级</option>
          </select>

          <button
            type="button"
            className={`chip-btn ${shadows ? "active" : ""}`}
            onClick={() => setShadows((value) => !value)}
          >
            阴影
          </button>
          <select
            className="chip-select"
            title="阴影贴图分辨率"
            disabled={!shadows}
            value={shadowQuality}
            onChange={(event) => setShadowQuality(event.target.value as ShadowQuality)}
          >
            {SHADOW_QUALITIES.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <StudioPanel
        open={studioOpen}
        onClose={() => setStudioOpen(false)}
        viewer={viewer}
        nodes={nodeList}
        selectedNode={selectedNode}
        onSelectNode={(id) => viewer?.selectNode(id)}
      />

      {stats && status === "ready" && (
        <div className="stage-stats">
          <span>{stats.triangles.toLocaleString()} 三角面</span>
          <span>{stats.meshes} 网格</span>
          <span>{stats.textures} 贴图</span>
          <span>
            {stats.size[0]} × {stats.size[1]} × {stats.size[2]} m
          </span>
        </div>
      )}

      {!url && status === "idle" && (
        <div className="stage-empty">
          <div className="stage-empty-mark">FB</div>
          <h2>尚未生成建筑</h2>
          <p>在右侧调整体量、风格与 PBR 贴图集，点击「生成建筑」即可在本机 Blender 中构建。</p>
        </div>
      )}

      {status === "loading" && (
        <div className="stage-overlay">
          <span className="spinner" />
          <p>正在加载模型...</p>
        </div>
      )}

      {status === "error" && (
        <div className="stage-overlay error">
          <p>预览加载失败</p>
          <code>{message}</code>
        </div>
      )}
    </section>
  );
}
