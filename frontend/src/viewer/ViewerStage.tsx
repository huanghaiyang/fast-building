import { useEffect, useRef, useState } from "react";
import { BuildingViewer, ViewerStats, ViewerStatus } from "./BuildingViewer";

interface Props {
  url: string | null;
}

/** 3D 预览舞台：包含画布、视角工具条与模型统计浮层。 */
export function ViewerStage({ url }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<BuildingViewer | null>(null);
  const [status, setStatus] = useState<ViewerStatus>("idle");
  const [message, setMessage] = useState<string>("");
  const [stats, setStats] = useState<ViewerStats | null>(null);
  const [autoRotate, setAutoRotate] = useState(true);
  const [wireframe, setWireframe] = useState(false);

  useEffect(() => {
    if (!hostRef.current) return;
    const viewer = new BuildingViewer(hostRef.current);
    viewerRef.current = viewer;
    return () => {
      viewer.dispose();
      viewerRef.current = null;
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
      },
    );
  }, [url]);

  useEffect(() => {
    viewerRef.current?.setAutoRotate(autoRotate);
  }, [autoRotate]);

  useEffect(() => {
    viewerRef.current?.setWireframe(wireframe);
  }, [wireframe]);

  return (
    <section className="stage">
      <div className="stage-canvas" ref={hostRef} />

      <div className="stage-toolbar">
        <button
          type="button"
          className={`chip-btn ${autoRotate ? "active" : ""}`}
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
      </div>

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
