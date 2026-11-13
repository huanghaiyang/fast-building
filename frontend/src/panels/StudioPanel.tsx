/**
 * 实时工作室面板：节点拾取 / 单节点材质 / PBR 污渍 / 天气 / 剖切 / 形变 / 碎裂 / 搭建。
 *
 * 面板本身只维护 UI 状态，所有预览效果直接调用 BuildingViewer 的实时接口。
 */

import { useEffect, useMemo, useState } from "react";
import {
  AttractorItem,
  BlockInfo,
  BuildingViewer,
  ClipAxis,
  ClipSettings,
  FractureSettings,
  GrungeSettings,
  NodeInfo,
  NodeMaterialState,
  RoughnessSettings,
  SunSettings,
  SurfaceSettings,
  VolumetricSettings,
} from "../viewer/BuildingViewer";

interface Props {
  open: boolean;
  onClose: () => void;
  viewer: BuildingViewer | null;
  nodes: NodeInfo[];
  selectedNode: NodeInfo | null;
  onSelectNode: (id: string | null) => void;
}

type Tab = "node" | "fx" | "build";

interface SliderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit?: string;
  onChange: (value: number) => void;
}

function Slider({ label, value, min, max, step, unit, onChange }: SliderProps) {
  return (
    <label className="studio-field">
      <span>
        {label}
        <b>
          {value.toFixed(step < 1 ? 2 : 0)}
          {unit ?? ""}
        </b>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="studio-check">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span>{label}</span>
    </label>
  );
}

const DEFAULT_MATERIAL: NodeMaterialState = {
  color: "#c9b79a",
  roughness: 0.7,
  metalness: 0.05,
  emissive: "#000000",
  emissiveIntensity: 0,
  normalScale: 1,
  envMapIntensity: 1,
  opacity: 1,
  transparent: false,
};

let attractorSeq = 0;

/** 三角面比例档位：只在预览中简化网格。 */
const TRIANGLE_RATIOS: Array<{ value: number; label: string }> = [
  { value: 1, label: "原始" },
  { value: 0.75, label: "75%" },
  { value: 0.5, label: "50%" },
  { value: 0.25, label: "25%" },
];

/** 灵活搭建的常用模块预设：点击即可在舞台中添加。 */
const BLOCK_PRESETS: Array<{
  name: string;
  size: [number, number, number];
  color: string;
}> = [
  { name: "墙体", size: [3.2, 2.8, 0.3], color: "#d8ccb6" },
  { name: "楼板", size: [4, 0.3, 4], color: "#b6ada0" },
  { name: "立柱", size: [0.45, 3, 0.45], color: "#c8bfae" },
  { name: "窗洞模块", size: [1.6, 1.6, 0.25], color: "#7d9cad" },
  { name: "体块", size: [2.2, 2.6, 2.2], color: "#c9b79a" },
];

interface NodeTreeGroup {
  key: string;
  label: string;
  groups: NodeTreeGroup[];
  leaves: NodeInfo[];
}

function buildNodeTree(nodes: NodeInfo[]): NodeTreeGroup {
  const root: NodeTreeGroup = { key: "", label: "根节点", groups: [], leaves: [] };
  for (const node of nodes) {
    let current = root;
    const path = node.path.length ? node.path : ["未分组"];
    path.forEach((label, depth) => {
      const key = path.slice(0, depth + 1).join("/");
      let group = current.groups.find((item) => item.key === key);
      if (!group) {
        group = { key, label, groups: [], leaves: [] };
        current.groups.push(group);
      }
      current = group;
    });
    current.leaves.push(node);
  }
  return root;
}

function countTreeLeaves(group: NodeTreeGroup): number {
  return group.groups.reduce((sum, item) => sum + countTreeLeaves(item), group.leaves.length);
}

/** 节点树：按模型层级分组，默认全部展开，可折叠。 */
function NodeTree({
  nodes,
  selectedId,
  onSelect,
  onHover,
  getTriangles,
}: {
  nodes: NodeInfo[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onHover: (id: string | null) => void;
  getTriangles: (id: string) => number;
}) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const tree = useMemo(() => buildNodeTree(nodes), [nodes]);

  const toggle = (key: string) => {
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const renderGroup = (group: NodeTreeGroup, depth: number) => {
    const leafDepth = group.key ? depth + 1 : depth;
    const hidden = group.key !== "" && collapsed.has(group.key);
    return (
      <div key={group.key || "root"}>
        {group.key !== "" && (
          <button
            type="button"
            className="studio-tree-group"
            style={{ paddingLeft: 4 + depth * 12 }}
            onClick={() => toggle(group.key)}
          >
            <span className="studio-tree-caret">{hidden ? "▸" : "▾"}</span>
            <span className="studio-tree-label">{group.label}</span>
            <em>{countTreeLeaves(group)}</em>
          </button>
        )}
        {!hidden && (
          <>
            {group.groups.map((child) => renderGroup(child, leafDepth))}
            {group.leaves.map((node) => (
              <button
                key={node.id}
                type="button"
                className={`studio-node ${selectedId === node.id ? "active" : ""}`}
                style={{ paddingLeft: 6 + leafDepth * 12 }}
                onMouseEnter={() => onHover(node.id)}
                onFocus={() => onHover(node.id)}
                onBlur={() => onHover(null)}
                onClick={() => onSelect(node.id)}
              >
                <i className="studio-node-dot" />
                <span>{node.name}</span>
                <em>{(getTriangles(node.id) || node.triangles).toLocaleString()} 面</em>
              </button>
            ))}
          </>
        )}
      </div>
    );
  };

  return (
    <div className="studio-node-list" onMouseLeave={() => onHover(null)}>
      {nodes.length === 0 && <p className="studio-hint">加载模型后可在此选择节点。</p>}
      {renderGroup(tree, 0)}
    </div>
  );
}

export function StudioPanel({ open, onClose, viewer, nodes, selectedNode, onSelectNode }: Props) {
  const [tab, setTab] = useState<Tab>("node");

  const [material, setMaterial] = useState<NodeMaterialState>(DEFAULT_MATERIAL);
  useEffect(() => {
    if (!viewer || !selectedNode) return;
    const state = viewer.getNodeMaterialState(selectedNode.id);
    if (state) setMaterial(state);
  }, [viewer, selectedNode]);

  const patchMaterial = (patch: Partial<NodeMaterialState>) => {
    if (!viewer || !selectedNode) return;
    setMaterial((current) => ({ ...current, ...patch }));
    viewer.setNodeMaterial(selectedNode.id, patch);
  };

  const [overallRatio, setOverallRatio] = useState(1);
  const [nodeRatios, setNodeRatios] = useState<Record<string, number>>({});

  useEffect(() => {
    setOverallRatio(1);
    setNodeRatios({});
  }, [nodes]);

  const applyOverallRatio = (ratio: number) => {
    setOverallRatio(ratio);
    viewer?.setSimplifyOverall(ratio);
  };

  const applyNodeRatio = (id: string, ratio: number) => {
    setNodeRatios((current) => ({ ...current, [id]: ratio }));
    viewer?.setNodeSimplify(id, ratio);
  };

  const [roughness, setRoughness] = useState<RoughnessSettings>({
    enabled: false,
    scale: 6,
    strength: 0.6,
  });
  useEffect(() => {
    viewer?.setRoughness(roughness);
  }, [viewer, roughness]);

  const [grunge, setGrunge] = useState<GrungeSettings>({
    enabled: false,
    strength: 0.55,
    scale: 3,
    color: "#2f2a24",
    roughness: 0.45,
  });
  useEffect(() => {
    viewer?.setGrunge(grunge);
  }, [viewer, grunge]);

  const [surface, setSurface] = useState<SurfaceSettings>({
    subsurface: 0.35,
    subsurfaceColor: "#c96a3f",
    diffuseWrap: 0.4,
  });
  useEffect(() => {
    viewer?.setSurface(surface);
  }, [viewer, surface]);

  const [rain, setRain] = useState({ intensity: 0, wetness: 0.35, flow: 0.6 });
  useEffect(() => {
    viewer?.setRain(rain.intensity);
    viewer?.setWetness(rain.wetness);
    viewer?.setWetFlow(rain.flow);
  }, [viewer, rain]);

  // ---------------------------------------------------------------- 雪景
  const [snow, setSnow] = useState({ intensity: 0, cover: 0, auto: true });
  useEffect(() => {
    viewer?.setSnow(snow.intensity);
    viewer?.setSnowAuto(snow.auto);
    if (!snow.auto) viewer?.setSnowCover(snow.cover);
  }, [viewer, snow]);

  // 自动积雪时覆盖度由预览器推进，这里按固定频率同步回滑块
  useEffect(() => {
    if (!viewer || !snow.auto) return;
    const timer = window.setInterval(() => {
      const current = viewer.getSnow();
      setSnow((state) =>
        Math.abs(state.cover - current.cover) < 0.005 ? state : { ...state, cover: current.cover },
      );
    }, 500);
    return () => window.clearInterval(timer);
  }, [viewer, snow.auto]);

  // ---------------------------------------------------------------- 昼夜循环
  const [sunCycle, setSunCycle] = useState({ enabled: false, speed: 0.15 });
  const [hour, setHour] = useState(10);
  useEffect(() => {
    viewer?.setSunCycle(sunCycle.enabled, sunCycle.speed);
  }, [viewer, sunCycle]);
  useEffect(() => {
    if (!viewer) return;
    const sync = (nextHour: number) => setHour(nextHour);
    viewer.onDayTimeChange = sync;
    setHour(viewer.getHour());
    return () => {
      if (viewer.onDayTimeChange === sync) viewer.onDayTimeChange = null;
    };
  }, [viewer]);

  // ---------------------------------------------------------------- 动态构件
  const [wheelSpin, setWheelSpin] = useState(true);
  const [openAll, setOpenAll] = useState(false);
  const [counts, setCounts] = useState({ openables: 0, wheels: 0 });
  useEffect(() => {
    viewer?.setWaterwheelSpin(wheelSpin);
  }, [viewer, wheelSpin]);
  useEffect(() => {
    if (!viewer) return;
    setCounts({ openables: viewer.getOpenableCount(), wheels: viewer.getWaterwheelCount() });
    viewer.setOpenables(openAll);
  }, [viewer, nodes, openAll]);

  const [volumetric, setVolumetric] = useState<VolumetricSettings>({
    enabled: false,
    intensity: 0.8,
  });
  useEffect(() => {
    viewer?.setVolumetric(volumetric);
  }, [viewer, volumetric]);

  // 阳光角度由预览器持有：环境切换时它会回调，保证滑块与画面一致
  const [sun, setSun] = useState<SunSettings | null>(null);
  useEffect(() => {
    if (!viewer) return;
    const sync = (next: SunSettings) =>
      setSun((current) =>
        current && current.azimuth === next.azimuth && current.elevation === next.elevation
          ? current
          : next,
      );
    sync(viewer.getSun());
    viewer.onSunChange = sync;
    return () => {
      if (viewer.onSunChange === sync) viewer.onSunChange = null;
    };
  }, [viewer]);
  useEffect(() => {
    if (!viewer || !sun) return;
    viewer.setSun(sun);
  }, [viewer, sun]);

  const [clip, setClip] = useState<ClipSettings>({
    enabled: false,
    axis: "x",
    position: 0,
    flipped: false,
  });
  const [clipRange, setClipRange] = useState<[number, number]>([-8, 8]);
  const [clipDrag, setClipDrag] = useState(false);

  useEffect(() => {
    if (!viewer) return;
    const range = viewer.getClipRange(clip.axis);
    setClipRange(range);
    setClip((current) => ({ ...current, position: (range[0] + range[1]) / 2 }));
  }, [viewer, nodes, clip.axis]);

  useEffect(() => {
    viewer?.setClip(clip);
  }, [viewer, clip]);

  useEffect(() => {
    viewer?.setClipDragMode(clipDrag);
  }, [viewer, clipDrag]);

  useEffect(() => {
    if (!viewer) return;
    const handler = (position: number) =>
      setClip((current) => ({ ...current, position }));
    viewer.onClipPosition = handler;
    return () => {
      if (viewer.onClipPosition === handler) viewer.onClipPosition = null;
    };
  }, [viewer]);

  const [attractorEnabled, setAttractorEnabled] = useState(false);
  const [attractors, setAttractors] = useState<AttractorItem[]>([]);
  const [pickId, setPickId] = useState<string | null>(null);

  useEffect(() => {
    viewer?.setAttractors(attractors, attractorEnabled);
  }, [viewer, attractors, attractorEnabled]);

  useEffect(() => {
    viewer?.setAttractorPickMode(pickId !== null, pickId);
  }, [viewer, pickId]);

  useEffect(() => {
    if (!viewer) return;
    const handler = (id: string, point: [number, number, number]) => {
      setAttractors((current) =>
        current.map((item) => (item.id === id ? { ...item, point, enabled: true } : item)),
      );
      setPickId(null);
    };
    viewer.onAttractorPicked = handler;
    viewer.onAttractorMoved = handler;
    return () => {
      if (viewer.onAttractorPicked === handler) viewer.onAttractorPicked = null;
      if (viewer.onAttractorMoved === handler) viewer.onAttractorMoved = null;
    };
  }, [viewer]);

  const addAttractor = () => {
    attractorSeq += 1;
    const spawn = viewer?.getAttractorSpawn() ?? ([0, 3, 0] as [number, number, number]);
    setAttractors((current) => [
      ...current,
      {
        id: `attractor-${attractorSeq}`,
        mode: "attract",
        strength: 1.6,
        radius: 4,
        point: [spawn[0], spawn[1], spawn[2] + current.length * 1.5],
        enabled: true,
      },
    ]);
    setAttractorEnabled(true);
  };

  const patchAttractor = (id: string, patch: Partial<AttractorItem>) => {
    setAttractors((current) =>
      current.map((item) => (item.id === id ? { ...item, ...patch } : item)),
    );
  };

  const removeAttractor = (id: string) => {
    setAttractors((current) => current.filter((item) => item.id !== id));
    if (pickId === id) setPickId(null);
  };

  const [fracture, setFracture] = useState<FractureSettings>({
    enabled: false,
    amount: 0.6,
    cell: 0.42,
    collapse: false,
    impulse: 1.2,
  });
  useEffect(() => {
    viewer?.setFracture(fracture);
  }, [viewer, fracture]);

  const [buildMode, setBuildMode] = useState(false);
  const [blocks, setBlocks] = useState<BlockInfo[]>([]);
  const [selectedBlock, setSelectedBlock] = useState<BlockInfo | null>(null);

  useEffect(() => {
    viewer?.setBuildMode(buildMode);
  }, [viewer, buildMode]);

  useEffect(() => {
    if (!viewer) return;
    const onBlocks = (next: BlockInfo[]) => setBlocks(next);
    const onBlock = (next: BlockInfo | null) => setSelectedBlock(next);
    viewer.onBlocksChanged = onBlocks;
    viewer.onSelectedBlock = onBlock;
    setBlocks(viewer.listBlocks());
    return () => {
      if (viewer.onBlocksChanged === onBlocks) viewer.onBlocksChanged = null;
      if (viewer.onSelectedBlock === onBlock) viewer.onSelectedBlock = null;
    };
  }, [viewer]);

  const updateBlock = (patch: {
    position?: [number, number, number];
    size?: [number, number, number];
    color?: string;
  }) => {
    if (!viewer || !selectedBlock) return;
    viewer.updateBlock(selectedBlock.id, patch);
    setSelectedBlock({ ...selectedBlock, ...patch });
  };

  const resetClipPosition = () => {
    const range = viewer?.getClipRange(clip.axis) ?? clipRange;
    setClipRange(range);
    setClip((current) => ({ ...current, position: (range[0] + range[1]) / 2 }));
  };

  return (
    <aside className={`studio ${open ? "open" : ""}`}>
      <div className="studio-head">
        <div>
          <h3>实时工作室</h3>
          <p>点选节点 · 即时预览</p>
        </div>
        <button type="button" className="studio-close" onClick={onClose} title="收起">
          ×
        </button>
      </div>

      <div className="studio-tabs">
        <button
          type="button"
          className={tab === "node" ? "active" : ""}
          onClick={() => setTab("node")}
        >
          节点与材质
        </button>
        <button
          type="button"
          className={tab === "fx" ? "active" : ""}
          onClick={() => setTab("fx")}
        >
          环境与特效
        </button>
        <button
          type="button"
          className={tab === "build" ? "active" : ""}
          onClick={() => setTab("build")}
        >
          灵活搭建
        </button>
      </div>

      <div className="studio-body">
        {tab === "node" && (
          <>
            <section className="studio-section">
              <h4>节点选择器</h4>
              <p className="studio-hint">
                在画面中点击任意网格即可选中；选中后直接调整材质，所见即所得。
              </p>
              <NodeTree
                nodes={nodes}
                selectedId={selectedNode?.id ?? null}
                onSelect={onSelectNode}
                onHover={(id) => viewer?.hoverNode(id)}
                getTriangles={(id) => viewer?.getNodeTriangleCount(id) ?? 0}
              />
              {selectedNode && (
                <div className="studio-meta">
                  <span>{selectedNode.material}</span>
                  <span>
                    {(
                      viewer?.getNodeTriangleCount(selectedNode.id) ?? selectedNode.triangles
                    ).toLocaleString()}{" "}
                    三角面
                  </span>
                </div>
              )}
            </section>

            <section className="studio-section">
              <h4>三角面调整</h4>
              <div className="studio-ratio">
                <span>整体</span>
                <div className="studio-ratio-group">
                  {TRIANGLE_RATIOS.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      className={`studio-ratio-btn ${overallRatio === option.value ? "active" : ""}`}
                      onClick={() => applyOverallRatio(option.value)}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className={`studio-ratio ${selectedNode ? "" : "studio-disabled"}`}>
                <span>当前节点</span>
                <div className="studio-ratio-group">
                  {TRIANGLE_RATIOS.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      className={`studio-ratio-btn ${
                        selectedNode && (nodeRatios[selectedNode.id] ?? 1) === option.value
                          ? "active"
                          : ""
                      }`}
                      onClick={() => selectedNode && applyNodeRatio(selectedNode.id, option.value)}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>
              <p className="studio-hint">
                {selectedNode
                  ? "可单独降低该节点面数，其余节点跟随整体档位；仅影响预览，不改变导出模型。"
                  : "选择节点后可单独降低该节点面数；整体档位作用于其余节点。"}
              </p>
            </section>

            <section className="studio-section">
              <h4>单节点材质</h4>
              {!selectedNode && <p className="studio-hint">先选择一个节点，材质修改只影响该节点。</p>}
              <div className={selectedNode ? "" : "studio-disabled"}>
                <label className="studio-field">
                  <span>基色</span>
                  <input
                    type="color"
                    value={material.color}
                    onChange={(event) => patchMaterial({ color: event.target.value })}
                  />
                </label>
                <Slider
                  label="粗糙度"
                  value={material.roughness}
                  min={0.05}
                  max={1}
                  step={0.01}
                  onChange={(value) => patchMaterial({ roughness: value })}
                />
                <Slider
                  label="金属度"
                  value={material.metalness}
                  min={0}
                  max={1}
                  step={0.01}
                  onChange={(value) => patchMaterial({ metalness: value })}
                />
                <Slider
                  label="法线强度"
                  value={material.normalScale}
                  min={0}
                  max={2}
                  step={0.02}
                  onChange={(value) => patchMaterial({ normalScale: value })}
                />
                <Slider
                  label="环境反射（IBL）"
                  value={material.envMapIntensity}
                  min={0}
                  max={3}
                  step={0.05}
                  onChange={(value) => patchMaterial({ envMapIntensity: value })}
                />
                <Slider
                  label="不透明度"
                  value={material.opacity}
                  min={0.05}
                  max={1}
                  step={0.01}
                  onChange={(value) => patchMaterial({ opacity: value, transparent: value < 1 })}
                />
                <Toggle
                  label="启用透明混合"
                  checked={material.transparent}
                  onChange={(transparent) => patchMaterial({ transparent })}
                />
                <SanitizedColor
                  label="自发光"
                  value={material.emissive}
                  onChange={(value) => patchMaterial({ emissive: value })}
                />
                <Slider
                  label="自发光强度"
                  value={material.emissiveIntensity}
                  min={0}
                  max={3}
                  step={0.05}
                  onChange={(value) => patchMaterial({ emissiveIntensity: value })}
                />
                <button
                  type="button"
                  className="studio-btn wide"
                  disabled={!selectedNode}
                  onClick={() => {
                    if (!viewer || !selectedNode) return;
                    viewer.resetNodeMaterial(selectedNode.id);
                    const state = viewer.getNodeMaterialState(selectedNode.id);
                    if (state) setMaterial(state);
                  }}
                >
                  恢复该节点原始材质
                </button>
              </div>
            </section>

            <section className="studio-section">
              <h4>表面散射</h4>
              <Slider
                label="次表面散射"
                value={surface.subsurface}
                min={0}
                max={1}
                step={0.01}
                onChange={(value) => setSurface((current) => ({ ...current, subsurface: value }))}
              />
              <Slider
                label="漫反射包裹"
                value={surface.diffuseWrap}
                min={0}
                max={1}
                step={0.01}
                onChange={(value) => setSurface((current) => ({ ...current, diffuseWrap: value }))}
              />
              <label className="studio-field">
                <span>散射颜色</span>
                <input
                  type="color"
                  value={surface.subsurfaceColor}
                  onChange={(event) =>
                    setSurface((current) => ({ ...current, subsurfaceColor: event.target.value }))
                  }
                />
              </label>
              <p className="studio-hint">
                次表面散射让背光面透出石材/木材的内层颜色，漫反射包裹柔化明暗交界；作用于全部节点。
              </p>
            </section>

            <section className="studio-section">
              <h4>粗糙度贴图</h4>
              <Toggle
                label="叠加程序化粗糙度"
                checked={roughness.enabled}
                onChange={(enabled) => setRoughness((current) => ({ ...current, enabled }))}
              />
              <Slider
                label="平铺尺度"
                value={roughness.scale}
                min={1}
                max={20}
                step={0.5}
                onChange={(value) => setRoughness((current) => ({ ...current, scale: value }))}
              />
              <Slider
                label="基础粗糙度"
                value={roughness.strength}
                min={0.05}
                max={1}
                step={0.01}
                onChange={(value) => setRoughness((current) => ({ ...current, strength: value }))}
              />
              <p className="studio-hint">粗糙度贴图作用于全部节点，与材质原有贴图叠加。</p>
            </section>

            <section className="studio-section">
              <h4>PBR 污渍</h4>
              <Toggle
                label="启用污渍遮罩"
                checked={grunge.enabled}
                onChange={(enabled) => setGrunge((current) => ({ ...current, enabled }))}
              />
              <Slider
                label="污渍强度"
                value={grunge.strength}
                min={0}
                max={1}
                step={0.01}
                onChange={(value) => setGrunge((current) => ({ ...current, strength: value }))}
              />
              <Slider
                label="污渍尺度"
                value={grunge.scale}
                min={0.5}
                max={10}
                step={0.1}
                onChange={(value) => setGrunge((current) => ({ ...current, scale: value }))}
              />
              <Slider
                label="粗糙度扰动"
                value={grunge.roughness}
                min={0}
                max={1}
                step={0.01}
                onChange={(value) => setGrunge((current) => ({ ...current, roughness: value }))}
              />
              <label className="studio-field">
                <span>污渍颜色</span>
                <input
                  type="color"
                  value={grunge.color}
                  onChange={(event) =>
                    setGrunge((current) => ({ ...current, color: event.target.value }))
                  }
                />
              </label>
            </section>
          </>
        )}

        {tab === "fx" && (
          <>
            <section className="studio-section">
              <h4>吸引子 / 排斥子</h4>
              <div className="studio-row">
                <Toggle
                  label="启用量场形变"
                  checked={attractorEnabled}
                  onChange={setAttractorEnabled}
                />
                <button type="button" className="studio-btn" onClick={addAttractor}>
                  + 新增
                </button>
              </div>
              {attractors.length === 0 && (
                <p className="studio-hint">暂无作用点；新增后可分别调整类型、强度、半径与作用点。</p>
              )}
              {attractors.length > 0 && (
                <p className="studio-hint">
                  画面中的圆点即作用点，直接拖拽即可移动；线框球表示影响半径，「拾取」后再点模型表面可精确落点。
                </p>
              )}
              {attractors.map((item, index) => (
                <div
                  key={item.id}
                  className={`studio-attractor ${pickId === item.id ? "active" : ""}`}
                >
                  <div className="studio-attractor-head">
                    <strong>
                      {item.mode === "attract" ? "吸引子" : "排斥子"} {index + 1}
                    </strong>
                    <button
                      type="button"
                      className="studio-btn danger small"
                      onClick={() => removeAttractor(item.id)}
                    >
                      删除
                    </button>
                  </div>
                  <div className="studio-seg">
                    <button
                      type="button"
                      className={item.mode === "attract" ? "active" : ""}
                      onClick={() => patchAttractor(item.id, { mode: "attract", enabled: true })}
                    >
                      塌陷（吸引）
                    </button>
                    <button
                      type="button"
                      className={item.mode === "repel" ? "active" : ""}
                      onClick={() => patchAttractor(item.id, { mode: "repel", enabled: true })}
                    >
                      膨胀（排斥）
                    </button>
                  </div>
                  <Slider
                    label="强度"
                    value={item.strength}
                    min={0}
                    max={5}
                    step={0.05}
                    onChange={(value) => patchAttractor(item.id, { strength: value })}
                  />
                  <Slider
                    label="影响半径"
                    value={item.radius}
                    min={0.5}
                    max={12}
                    step={0.1}
                    unit=" m"
                    onChange={(value) => patchAttractor(item.id, { radius: value })}
                  />
                  <div className="studio-row">
                    <button
                      type="button"
                      className={`studio-btn ${pickId === item.id ? "active" : ""}`}
                      onClick={() => setPickId(pickId === item.id ? null : item.id)}
                    >
                      {pickId === item.id ? "点击画面取点…" : "拾取作用点"}
                    </button>
                    <Toggle
                      label="启用"
                      checked={item.enabled}
                      onChange={(enabled) => patchAttractor(item.id, { enabled })}
                    />
                  </div>
                  {(["x", "y", "z"] as const).map((axis, axisIndex) => (
                    <Slider
                      key={axis}
                      label={`作用点 ${axis.toUpperCase()}`}
                      value={item.point[axisIndex]}
                      min={-12}
                      max={16}
                      step={0.1}
                      unit=" m"
                      onChange={(value) => {
                        const point = [...item.point] as [number, number, number];
                        point[axisIndex] = value;
                        patchAttractor(item.id, { point });
                      }}
                    />
                  ))}
                </div>
              ))}
            </section>

            {sun && (
              <section className="studio-section">
                <h4>阳光与昼夜</h4>
                {!sunCycle.enabled && (
                  <>
                    <Slider
                      label="方位角"
                      value={Math.round(sun.azimuth)}
                      min={0}
                      max={360}
                      step={1}
                      unit="°"
                      onChange={(azimuth) =>
                        setSun((current) => (current ? { ...current, azimuth } : current))
                      }
                    />
                    <Slider
                      label="高度角"
                      value={Math.round(sun.elevation)}
                      min={0}
                      max={90}
                      step={1}
                      unit="°"
                      onChange={(elevation) =>
                        setSun((current) => (current ? { ...current, elevation } : current))
                      }
                    />
                  </>
                )}
                <Toggle
                  label="真实昼夜循环（东升西落）"
                  checked={sunCycle.enabled}
                  onChange={(enabled) => setSunCycle((current) => ({ ...current, enabled }))}
                />
                {sunCycle.enabled && (
                  <>
                    <Slider
                      label="时间推进"
                      value={sunCycle.speed}
                      min={0.01}
                      max={0.6}
                      step={0.01}
                      unit=" h/s"
                      onChange={(speed) => setSunCycle((current) => ({ ...current, speed }))}
                    />
                    <Slider
                      label="当前时间"
                      value={hour}
                      min={0}
                      max={24}
                      step={0.05}
                      unit=" 点"
                      onChange={(value) => {
                        setHour(value);
                        viewer?.setHour(value);
                      }}
                    />
                  </>
                )}
                <p className="studio-hint">
                  方位角绕建筑旋转太阳，高度角决定日照角度；开启昼夜循环后按时段自动调整主光强度/色温、
                  天空渐变、雾与环境光，夜晚出现星点与冷色月光。
                </p>
              </section>
            )}

            <section className="studio-section">
              <h4>体积光透视</h4>
              <Toggle
                label="启用体积光（丁达尔光柱）"
                checked={volumetric.enabled}
                onChange={(enabled) => setVolumetric((current) => ({ ...current, enabled }))}
              />
              <Slider
                label="光柱强度"
                value={volumetric.intensity}
                min={0}
                max={2}
                step={0.02}
                onChange={(value) => setVolumetric((current) => ({ ...current, intensity: value }))}
              />
              <p className="studio-hint">
                沿太阳方向生成光柱与浮尘，被建筑遮挡后形成体积透视；切换环境会同步改变光向。
              </p>
            </section>

            <section className="studio-section">
              <h4>雨天</h4>
              <Slider
                label="雨量"
                value={rain.intensity}
                min={0}
                max={1}
                step={0.01}
                onChange={(value) => setRain((current) => ({ ...current, intensity: value }))}
              />
              <Slider
                label="表面湿度"
                value={rain.wetness}
                min={0}
                max={1}
                step={0.01}
                onChange={(value) => setRain((current) => ({ ...current, wetness: value }))}
              />
              <Slider
                label="雨水流动"
                value={rain.flow}
                min={0}
                max={1}
                step={0.01}
                onChange={(value) => setRain((current) => ({ ...current, flow: value }))}
              />
              <p className="studio-hint">
                湿度让墙面与地面变暗、粗糙度下降；雨水流动沿重力方向产生动态水痕高光。
              </p>
            </section>

            <section className="studio-section">
              <h4>雪景</h4>
              <Slider
                label="降雪强度"
                value={snow.intensity}
                min={0}
                max={1}
                step={0.01}
                onChange={(value) => setSnow((current) => ({ ...current, intensity: value }))}
              />
              <Toggle
                label="自动积雪（停雪后缓慢融化）"
                checked={snow.auto}
                onChange={(auto) => setSnow((current) => ({ ...current, auto }))}
              />
              <Slider
                label="积雪覆盖"
                value={snow.cover}
                min={0}
                max={1}
                step={0.01}
                onChange={(value) => setSnow((current) => ({ ...current, cover: value }))}
              />
              <p className="studio-hint">
                雪优先落在朝上的屋面和地面，立面靠噪声形成挂雪边缘；自动积雪开启时覆盖度会随降雪慢慢累积，停雪后缓慢融化。
              </p>
            </section>

            <section className="studio-section">
              <h4>动态构件</h4>
              <Toggle
                label={`水轮转动${counts.wheels > 0 ? "" : "（当前模型无）"}`}
                checked={wheelSpin}
                onChange={setWheelSpin}
              />
              <div className="studio-seg">
                <button
                  type="button"
                  className={openAll ? "active" : ""}
                  onClick={() => setOpenAll(true)}
                >
                  门窗全开
                </button>
                <button
                  type="button"
                  className={openAll ? "" : "active"}
                  onClick={() => setOpenAll(false)}
                >
                  门窗全关
                </button>
              </div>
              <p className="studio-hint">
                画面中直接点击门扇 / 窗扇可单独开合（当前 {counts.openables} 个可动构件）；水轮绕自身轮轴持续转动。
              </p>
            </section>

            <section className="studio-section">
              <h4>横切面预览</h4>
              <Toggle
                label="启用剖切"
                checked={clip.enabled}
                onChange={(enabled) => setClip((current) => ({ ...current, enabled }))}
              />
              <div className="studio-seg">
                {(["x", "y", "z"] as ClipAxis[]).map((axis) => (
                  <button
                    key={axis}
                    type="button"
                    className={clip.axis === axis ? "active" : ""}
                    onClick={() => setClip((current) => ({ ...current, axis }))}
                  >
                    {axis.toUpperCase()} 轴
                  </button>
                ))}
                <button
                  type="button"
                  className={clip.flipped ? "active" : ""}
                  onClick={() => setClip((current) => ({ ...current, flipped: !current.flipped }))}
                >
                  翻转
                </button>
              </div>
              <Slider
                label="剖切位置"
                value={clip.position}
                min={clipRange[0]}
                max={clipRange[1]}
                step={0.05}
                unit=" m"
                onChange={(value) => setClip((current) => ({ ...current, position: value }))}
              />
              <div className="studio-row">
                <Toggle
                  label="鼠标拖动剖切面"
                  checked={clipDrag}
                  onChange={setClipDrag}
                />
                <button type="button" className="studio-btn" onClick={resetClipPosition}>
                  居中
                </button>
              </div>
              <p className="studio-hint">开启拖动后，在画面中上下拖动即可推进或回退剖切面。</p>
            </section>

            <section className="studio-section">
              <h4>体素碎裂</h4>
              <Toggle
                label="切换体素碎裂视图"
                checked={fracture.enabled}
                onChange={(enabled) => setFracture((current) => ({ ...current, enabled }))}
              />
              <Slider
                label="爆散程度"
                value={fracture.amount}
                min={0}
                max={5}
                step={0.05}
                onChange={(value) => setFracture((current) => ({ ...current, amount: value }))}
              />
              <Slider
                label="体素尺寸"
                value={fracture.cell}
                min={0.2}
                max={1.2}
                step={0.02}
                unit=" m"
                onChange={(value) => setFracture((current) => ({ ...current, cell: value }))}
              />
              <Toggle
                label="物理崩塌"
                checked={fracture.collapse}
                onChange={(collapse) => setFracture((current) => ({ ...current, collapse }))}
              />
              <Slider
                label="崩塌冲击"
                value={fracture.impulse}
                min={0.1}
                max={4}
                step={0.05}
                onChange={(value) => setFracture((current) => ({ ...current, impulse: value }))}
              />
              <button
                type="button"
                className="studio-btn wide"
                onClick={() => viewer?.triggerCollapse()}
                disabled={!fracture.enabled || !fracture.collapse}
              >
                重新崩塌
              </button>
              <p className="studio-hint">
                体素保留原模型贴图与 PBR 材质；开启物理崩塌后按重力落地、摩擦停稳。
              </p>
            </section>
          </>
        )}

        {tab === "build" && (
          <>
            <section className="studio-section">
              <h4>选取模块</h4>
              <div className="studio-presets">
                {BLOCK_PRESETS.map((preset) => (
                  <button
                    key={preset.name}
                    type="button"
                    className="studio-preset"
                    onClick={() => {
                      viewer?.addBlock({
                        name: preset.name,
                        size: preset.size,
                        color: preset.color,
                      });
                      setBuildMode(true);
                    }}
                  >
                    <i style={{ background: preset.color }} />
                    <span>{preset.name}</span>
                    <em>{preset.size.map((value) => value.toFixed(1)).join(" × ")}</em>
                  </button>
                ))}
              </div>
              <p className="studio-hint">点击预设即可添加模块，添加后可继续调整尺寸与位置。</p>
            </section>

            <section className="studio-section">
              <h4>灵活搭建</h4>
              <Toggle
                label="进入搭建模式（点击选择模块）"
                checked={buildMode}
                onChange={setBuildMode}
              />
              <p className="studio-hint">
                舞台交互：点击选中 · 拖动平移（按住 Shift 升降）· Alt + 点击地面新增 · Delete 删除。
              </p>
              <button
                type="button"
                className="studio-btn wide"
                onClick={() => viewer?.addBlock()}
              >
                + 添加体块模块
              </button>
              <div className="studio-block-list">
                {blocks.length === 0 && <p className="studio-hint">还没有模块，先添加一个体块。</p>}
                {blocks.map((block) => (
                  <button
                    key={block.id}
                    type="button"
                    className={`studio-block ${selectedBlock?.id === block.id ? "active" : ""}`}
                    onClick={() => viewer?.selectBlock(block.id)}
                  >
                    <i style={{ background: block.color }} />
                    <span>{block.name}</span>
                    <em>
                      {block.size[0].toFixed(1)} × {block.size[1].toFixed(1)} ×{" "}
                      {block.size[2].toFixed(1)}
                    </em>
                  </button>
                ))}
              </div>
            </section>

            <section className="studio-section">
              <h4>选中模块</h4>
              {!selectedBlock && <p className="studio-hint">开启搭建模式后，在画面中或上方列表选择模块。</p>}
              <div className={selectedBlock ? "" : "studio-disabled"}>
                {(["宽 W", "高 H", "深 D"] as const).map((label, index) => (
                  <Slider
                    key={label}
                    label={label}
                    value={selectedBlock?.size[index] ?? 2}
                    min={0.4}
                    max={10}
                    step={0.1}
                    unit=" m"
                    onChange={(value) => {
                      if (!selectedBlock) return;
                      const size = [...selectedBlock.size] as [number, number, number];
                      size[index] = value;
                      updateBlock({ size });
                    }}
                  />
                ))}
                {(["X", "Y", "Z"] as const).map((label, index) => (
                  <Slider
                    key={label}
                    label={`位置 ${label}`}
                    value={selectedBlock?.position[index] ?? 0}
                    min={-20}
                    max={24}
                    step={0.1}
                    unit=" m"
                    onChange={(value) => {
                      if (!selectedBlock) return;
                      const position = [...selectedBlock.position] as [number, number, number];
                      position[index] = value;
                      updateBlock({ position });
                    }}
                  />
                ))}
                <label className="studio-field">
                  <span>模块颜色</span>
                  <input
                    type="color"
                    value={selectedBlock?.color ?? "#c9b79a"}
                    onChange={(event) => updateBlock({ color: event.target.value })}
                  />
                </label>
                <div className="studio-expand">
                  <span>智能扩展</span>
                  <div className="studio-row">
                    {(["x", "y", "z"] as const).map((axis) => (
                      <button
                        key={axis}
                        type="button"
                        className="studio-btn"
                        disabled={!selectedBlock}
                        onClick={() => {
                          if (!selectedBlock) return;
                          viewer?.smartExpand(selectedBlock.id, axis);
                        }}
                      >
                        +{axis.toUpperCase()}
                      </button>
                    ))}
                  </div>
                  <p className="studio-hint">
                    沿轴向外延伸：有缝隙时自动补缝拼接，已贴合时追加同尺寸模块。
                  </p>
                </div>
                <div className="studio-row">
                  <button
                    type="button"
                    className="studio-btn"
                    disabled={!selectedBlock}
                    onClick={() => selectedBlock && viewer?.duplicateBlock(selectedBlock.id)}
                  >
                    复制
                  </button>
                  <button
                    type="button"
                    className="studio-btn danger"
                    disabled={!selectedBlock}
                    onClick={() => selectedBlock && viewer?.removeBlock(selectedBlock.id)}
                  >
                    删除
                  </button>
                </div>
              </div>
            </section>
          </>
        )}
      </div>
    </aside>
  );
}

/** 颜色输入需要 #rrggbb，自发光默认值为 #000000，这里做一次兜底。 */
function SanitizedColor({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="studio-field">
      <span>{label}</span>
      <input
        type="color"
        value={/^#[0-9a-f]{6}$/i.test(value) ? value : "#000000"}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}
