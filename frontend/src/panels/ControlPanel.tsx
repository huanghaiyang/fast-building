import { Footprint, JobView, Medieval, Openings, StyleInfo, TextureSet } from "../api/client";

interface Props {
  form: Footprint;
  onChange: (patch: Partial<Footprint>) => void;
  onOpeningsChange: (patch: Partial<Openings>) => void;
  onMedievalChange: (patch: Partial<Medieval>) => void;
  styles: StyleInfo[];
  textureSets: TextureSet[];
  job: JobView | null;
  busy: boolean;
  glbUrl: string | null;
  error: string | null;
  onGenerate: () => void;
  onCancel: () => void;
  onOpenUpload: () => void;
}

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
    <label className="field">
      <span className="field-label">
        {label}
        <b>
          {value}
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

export function ControlPanel(props: Props) {
  const {
    form,
    onChange,
    onOpeningsChange,
    onMedievalChange,
    styles,
    textureSets,
    job,
    busy,
    glbUrl,
    error,
    onGenerate,
    onCancel,
    onOpenUpload,
  } = props;

  const stats = job?.result?.stats;
  const progress = Math.round((job?.progress ?? 0) * 100);
  const running = job?.status === "running" || job?.status === "queued";

  return (
    <div className="panel-inner">
      <div className="panel-head">
        <div>
          <h2>生成参数</h2>
          <p className="panel-sub">体量 · 立面 · 材质</p>
        </div>
        <span className={`status-pill status-${job?.status ?? "idle"}`}>
          {job ? job.status.toUpperCase() : "待生成"}
        </span>
      </div>

      <section className="group">
        <h3>体量</h3>
        <div className="pair">
          <label className="field">
            <span className="field-label">宽度</span>
            <div className="input-wrap">
              <input
                type="number"
                min={6}
                max={60}
                step={0.5}
                value={form.width}
                onChange={(event) => onChange({ width: Number(event.target.value) })}
              />
              <span>m</span>
            </div>
          </label>
          <label className="field">
            <span className="field-label">进深</span>
            <div className="input-wrap">
              <input
                type="number"
                min={6}
                max={40}
                step={0.5}
                value={form.depth}
                onChange={(event) => onChange({ depth: Number(event.target.value) })}
              />
              <span>m</span>
            </div>
          </label>
        </div>
        <Slider
          label="开间数"
          value={form.bays}
          min={1}
          max={8}
          step={1}
          onChange={(value) => onChange({ bays: value })}
        />
        <Slider
          label="层数"
          value={form.floors}
          min={1}
          max={8}
          step={1}
          onChange={(value) => onChange({ floors: value })}
        />
        <Slider
          label="层高"
          value={form.floor_height}
          min={2.4}
          max={5}
          step={0.1}
          unit=" m"
          onChange={(value) => onChange({ floor_height: value })}
        />
      </section>

      <section className="group">
        <h3>屋顶</h3>
        <div className="segmented">
          <button
            type="button"
            className={form.roof === "gable" ? "active" : ""}
            onClick={() => onChange({ roof: "gable" })}
          >
            双坡
          </button>
          <button
            type="button"
            className={form.roof === "flat" ? "active" : ""}
            onClick={() => onChange({ roof: "flat" })}
          >
            平屋顶
          </button>
        </div>
        <Slider
          label="屋面坡度"
          value={form.roof_pitch}
          min={5}
          max={60}
          step={1}
          unit="°"
          onChange={(value) => onChange({ roof_pitch: value })}
        />
      </section>

      <section className="group">
        <h3>外观与材质</h3>
        <label className="field">
          <span className="field-label">风格预设</span>
          <select value={form.style} onChange={(event) => onChange({ style: event.target.value })}>
            {styles.map((style) => (
              <option key={style.id} value={style.id}>
                {style.name}
              </option>
            ))}
          </select>
        </label>

        <div className="field">
          <span className="field-label">
            PBR 贴图集
            <button type="button" className="link-btn" onClick={onOpenUpload}>
              导入 +
            </button>
          </span>
          <div className="texture-grid">
            {textureSets.map((set) => {
              const label = set.display_name ?? set.name;
              const active = set.id === form.textureset;
              return (
                <button
                  key={set.id}
                  type="button"
                  className={`texture-card ${active ? "active" : ""}`}
                  title={`${label} · 平铺 ${set.tile_m}m · ${set.resolution}px`}
                  onClick={() => onChange({ textureset: set.id })}
                >
                  <span className="texture-card-image">
                    {set.preview ? <img src={set.preview} alt={label} loading="lazy" /> : <i />}
                  </span>
                  <span className="texture-card-name">{label}</span>
                  <span className="texture-card-meta">{set.tile_m} m</span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="toggle-row">
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.balcony}
              onChange={(event) => onChange({ balcony: event.target.checked })}
            />
            <span>生成阳台</span>
          </label>
          <label className="seed">
            <span>随机种子</span>
            <input
              type="number"
              value={form.seed}
              onChange={(event) => onChange({ seed: Number(event.target.value) })}
            />
            <button
              type="button"
              className="link-btn"
              onClick={() => onChange({ seed: Math.floor(Math.random() * 10000) })}
            >
              换一个
            </button>
          </label>
        </div>
      </section>

      <details className="group collapsible">
        <summary>
          <h3>中世纪构件</h3>
          <span>展开</span>
        </summary>
        <div className="medieval-grid">
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.timber_frame}
              onChange={(event) => onMedievalChange({ timber_frame: event.target.checked })}
            />
            <span>木筋墙</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.arch_openings}
              onChange={(event) => onMedievalChange({ arch_openings: event.target.checked })}
            />
            <span>尖拱门窗</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.jetty}
              onChange={(event) => onMedievalChange({ jetty: event.target.checked })}
            />
            <span>悬挑楼层</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.crenellation}
              onChange={(event) => onMedievalChange({ crenellation: event.target.checked })}
            />
            <span>垛口女儿墙</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.chimney}
              onChange={(event) => onMedievalChange({ chimney: event.target.checked })}
            />
            <span>砖石烟囱</span>
          </label>
        </div>
        <Slider
          label="老虎窗（每坡）"
          value={form.medieval.dormers}
          min={0}
          max={2}
          step={1}
          onChange={(value) => onMedievalChange({ dormers: value })}
        />
        <p className="hint">垛口女儿墙仅平屋顶生效，老虎窗仅双坡生效。</p>
      </details>

      <details className="group collapsible">
        <summary>
          <h3>门窗尺寸</h3>
          <span>展开</span>
        </summary>
        <Slider
          label="窗宽"
          value={form.openings.window_w}
          min={0.6}
          max={3.2}
          step={0.1}
          unit=" m"
          onChange={(value) => onOpeningsChange({ window_w: value })}
        />
        <Slider
          label="窗高"
          value={form.openings.window_h}
          min={0.6}
          max={3.2}
          step={0.1}
          unit=" m"
          onChange={(value) => onOpeningsChange({ window_h: value })}
        />
        <Slider
          label="窗台高"
          value={form.openings.sill_h}
          min={0}
          max={1.8}
          step={0.05}
          unit=" m"
          onChange={(value) => onOpeningsChange({ sill_h: value })}
        />
        <Slider
          label="门宽"
          value={form.openings.door_w}
          min={0.7}
          max={2.4}
          step={0.05}
          unit=" m"
          onChange={(value) => onOpeningsChange({ door_w: value })}
        />
        <Slider
          label="门高"
          value={form.openings.door_h}
          min={1.8}
          max={3.4}
          step={0.05}
          unit=" m"
          onChange={(value) => onOpeningsChange({ door_h: value })}
        />
      </details>

      <div className="actions">
        <button type="button" className="btn primary" disabled={busy} onClick={onGenerate}>
          {busy ? "生成中..." : "生成建筑"}
        </button>
        {running && (
          <button type="button" className="btn ghost" onClick={onCancel}>
            取消
          </button>
        )}
      </div>

      {error && <div className="alert">{error}</div>}

      {job && (
        <section className="job">
          <div className="progress-head">
            <span>{job.stage || "处理中"}</span>
            <b>{progress}%</b>
          </div>
          <div className="progress">
            <div className="progress-bar" style={{ width: `${progress}%` }} />
          </div>

          {job.error && <div className="alert">{job.error}</div>}

          {stats && job.status === "succeeded" && (
            <div className="result-grid">
              <div>
                <span>顶点</span>
                <b>{stats.verts?.toLocaleString() ?? "-"}</b>
              </div>
              <div>
                <span>三角面</span>
                <b>{stats.tris?.toLocaleString() ?? "-"}</b>
              </div>
              <div>
                <span>构件</span>
                <b>{stats.objects ?? "-"}</b>
              </div>
              <div>
                <span>耗时</span>
                <b>{stats.seconds ?? "-"}s</b>
              </div>
              <div>
                <span>GLB</span>
                <b>{stats.glb_bytes ? `${(stats.glb_bytes / 1024 / 1024).toFixed(2)} MB` : "-"}</b>
              </div>
              <div>
                <span>任务</span>
                <b className="mono">{job.id.slice(-6)}</b>
              </div>
            </div>
          )}

          {glbUrl && (
            <a className="btn download" href={glbUrl} download="building.glb">
              下载 GLB 模型
            </a>
          )}

          <details className="logs">
            <summary>构建日志（{job.logs.length} 行）</summary>
            <pre>{job.logs.slice(-120).join("\n")}</pre>
          </details>
        </section>
      )}
    </div>
  );
}
