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
  /** 纯前端即时体量预览开关。 */
  quickPreview: boolean;
  onQuickPreviewChange: (value: boolean) => void;
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
    quickPreview,
    onQuickPreviewChange,
  } = props;

  /** 中世纪构件互斥规则：开启一项时自动关闭/置灰冲突项。 */
  const applyMedieval = (patch: Partial<Medieval>) => {
    const next: Partial<Medieval> = { ...patch };
    const on = (key: keyof Medieval) => patch[key] === true;

    if (on("thatch_roof")) next.slate_roof = false;
    if (on("slate_roof")) next.thatch_roof = false;
    if (on("log_walls")) next.timber_frame = false;
    if (on("timber_frame")) next.log_walls = false;
    if (on("arch_openings")) next.round_arch = false;
    if (on("round_arch")) next.arch_openings = false;

    // 街市立面的三种开间形态互斥（橱窗 / 马厩 / 仓门）
    const shopKeys = ["shopfront", "stable_bays", "barn_door"] as const;
    for (const key of shopKeys) {
      if (!on(key)) continue;
      for (const other of shopKeys) if (other !== key) next[other] = false;
    }

    // 瞭望棚替换整栋屋顶，与坡屋顶相关构件互斥
    if (on("lookout")) {
      next.dormers = 0;
      next.crenellation = false;
      next.bellcote = false;
      next.ruined_roof = false;
      next.bell_tower = false;
      next.nave_roof = false;
      next.thatch_roof = false;
      next.slate_roof = false;
    }

    // 整栋塌毁：清空全部依赖正常墙身/屋顶的构件
    if (on("collapsed")) {
      const clear: Array<keyof Medieval> = [
        "timber_frame", "log_walls", "thatch_roof", "slate_roof", "crenellation",
        "burnt", "water_wheel", "shopfront", "stable_bays", "barn_door", "shop_board",
        "jetty_brackets", "street_props", "ladder", "lookout", "hoarding",
        "stepped_base", "gallery", "ridge_cap", "shingle_band", "porch", "ivy", "chimney",
      ];
      for (const key of clear) (next as Record<string, unknown>)[key] = false;
      next.dormers = 0;
    }

    onMedievalChange(next);
  };

  const medieval = form.medieval;
  const gableRoof = form.roof === "gable";
  const flatRoof = form.roof === "flat";

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
                min={4}
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
                min={4}
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
        <h3>几何质量</h3>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={form.smooth}
            onChange={(event) => onChange({ smooth: event.target.checked })}
          />
          <span>平滑着色（按二面角保留硬边）</span>
        </label>
        <div className="field">
          <span className="field-label">细分级别</span>
          <div className="segmented three">
            {[
              { value: 0, label: "关" },
              { value: 1, label: "1 级" },
              { value: 2, label: "2 级" },
            ].map((option) => (
              <button
                key={option.value}
                type="button"
                className={form.subdiv === option.value ? "active" : ""}
                onClick={() => onChange({ subdiv: option.value })}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
        <p className="hint">
          墙面边缘已自动做柔和倒角；细分越高级曲面越圆润，但面数与文件体积同步上升，2 级仅建议近景查看。
        </p>
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

      <fieldset className="medieval-fieldset" disabled={medieval.collapsed}>
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
              disabled={medieval.collapsed || medieval.log_walls}
              onChange={(event) => applyMedieval({ timber_frame: event.target.checked })}
            />
            <span>木筋墙</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.arch_openings}
              disabled={medieval.collapsed || medieval.round_arch}
              onChange={(event) => applyMedieval({ arch_openings: event.target.checked })}
            />
            <span>尖拱门窗</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.jetty}
              onChange={(event) => applyMedieval({ jetty: event.target.checked })}
            />
            <span>悬挑楼层</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.crenellation}
              disabled={!flatRoof || medieval.collapsed}
              onChange={(event) => applyMedieval({ crenellation: event.target.checked })}
            />
            <span>垛口女儿墙</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.chimney}
              onChange={(event) => applyMedieval({ chimney: event.target.checked })}
            />
            <span>砖石烟囱</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.burnt}
              onChange={(event) => applyMedieval({ burnt: event.target.checked })}
            />
            <span>烧毁木构</span>
          </label>
        </div>
        <Slider
          label="老虎窗（每坡）"
          value={form.medieval.dormers}
          min={0}
          max={2}
          step={1}
          onChange={(value) => applyMedieval({ dormers: value })}
        />
        <p className="hint">垛口女儿墙仅平屋顶生效，老虎窗仅双坡生效；烧毁木构会把墙面烧出炭斑，并把屋顶换成只剩一坡茅草、一坡石瓦的残架。</p>
      </details>

      <details className="group collapsible">
        <summary>
          <h3>哥特石构与废墟</h3>
          <span>展开</span>
        </summary>
        <div className="medieval-grid">
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.buttresses}
              onChange={(event) => applyMedieval({ buttresses: event.target.checked })}
            />
            <span>石扶壁</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.bellcote}
              disabled={!gableRoof || medieval.collapsed}
              onChange={(event) => applyMedieval({ bellcote: event.target.checked })}
            />
            <span>屋脊石钟塔</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.ruined_roof}
              disabled={!gableRoof || medieval.collapsed}
              onChange={(event) => applyMedieval({ ruined_roof: event.target.checked })}
            />
            <span>破损屋顶</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.bell_tower}
              disabled={!gableRoof || medieval.collapsed}
              onChange={(event) => applyMedieval({ bell_tower: event.target.checked })}
            />
            <span>方形钟塔</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.nave_roof}
              disabled={!gableRoof || medieval.collapsed}
              onChange={(event) => applyMedieval({ nave_roof: event.target.checked })}
            />
            <span>纵向残顶</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.collapsed}
              onChange={(event) => applyMedieval({ collapsed: event.target.checked })}
            />
            <span>整栋塌毁</span>
          </label>
        </div>
        <p className="hint">
          扶壁沿开间分界贴在墙外；石钟塔仅双坡生效；破损屋顶会抽掉部分瓦面并露出椽条；整栋塌毁会把建筑换成残墙、瓦砾与焦木梁架，不再生成楼板与屋顶。方形钟塔在西端立起一座断顶石塔，纵向残顶把屋脊改到长轴并换成大面塌落、露椽的教堂屋顶。
        </p>
      </details>

      <details className="group collapsible">
        <summary>
          <h3>瞭望塔构件</h3>
          <span>展开</span>
        </summary>
        <div className="medieval-grid">
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.stepped_base}
              onChange={(event) => applyMedieval({ stepped_base: event.target.checked })}
            />
            <span>阶梯石台基</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.hoarding}
              onChange={(event) => applyMedieval({ hoarding: event.target.checked })}
            />
            <span>塔顶木挑廊</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.lookout}
              onChange={(event) => applyMedieval({ lookout: event.target.checked })}
            />
            <span>木构瞭望棚</span>
          </label>
        </div>
        <p className="hint">
          石台基为三级收分的条石塔座；挑廊由斜撑托架外挑并带木梯；瞭望棚会替换整栋坡屋顶，改为一间带瓦顶的木板小屋。
        </p>
      </details>

      <details className="group collapsible">
        <summary>
          <h3>半木构客栈</h3>
          <span>展开</span>
        </summary>
        <div className="medieval-grid">
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.gallery}
              onChange={(event) => applyMedieval({ gallery: event.target.checked })}
            />
            <span>环绕木廊</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.shop_sign}
              onChange={(event) => applyMedieval({ shop_sign: event.target.checked })}
            />
            <span>悬挑店招</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.ridge_cap}
              onChange={(event) => applyMedieval({ ridge_cap: event.target.checked })}
            />
            <span>脊梁与封檐板</span>
          </label>
        </div>
        <p className="hint">
          木廊沿二层前、左、右三面外挑一圈，带栏杆与斜撑；店招挂在门旁；脊梁两端探出山墙并补博风板。配合「木筋墙 + 悬挑楼层 + 破损屋顶」即得破败客栈。
        </p>
      </details>

      <details className="group collapsible">
        <summary>
          <h3>原木与茅草</h3>
          <span>展开</span>
        </summary>
        <div className="medieval-grid">
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.log_walls}
              disabled={medieval.collapsed || medieval.timber_frame}
              onChange={(event) => applyMedieval({ log_walls: event.target.checked })}
            />
            <span>圆木叠砌墙</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.thatch_roof}
              disabled={!gableRoof || medieval.collapsed || medieval.slate_roof}
              onChange={(event) => applyMedieval({ thatch_roof: event.target.checked })}
            />
            <span>厚茅草屋顶</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.shingle_band}
              onChange={(event) => applyMedieval({ shingle_band: event.target.checked })}
            />
            <span>石瓦腰带</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.stone_plinth}
              onChange={(event) => applyMedieval({ stone_plinth: event.target.checked })}
            />
            <span>毛石勒脚</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.porch}
              onChange={(event) => applyMedieval({ porch: event.target.checked })}
            />
            <span>茅草门廊</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.ivy}
              onChange={(event) => applyMedieval({ ivy: event.target.checked })}
            />
            <span>常春藤与花丛</span>
          </label>
        </div>
        {form.medieval.ivy && (
          <>
            <Slider
              label="藤蔓覆盖度"
              value={Math.round(form.medieval.ivy_coverage * 100)}
              min={5}
              max={100}
              step={5}
              unit="%"
              onChange={(value) => applyMedieval({ ivy_coverage: value / 100 })}
            />
            <Slider
              label="藤蔓生长高度"
              value={Math.round(form.medieval.ivy_height * 100)}
              min={5}
              max={100}
              step={5}
              unit="%"
              onChange={(value) => applyMedieval({ ivy_height: value / 100 })}
            />
            <p className="hint">覆盖度决定每面墙爬几股藤，高度按墙高百分比计算。</p>
          </>
        )}
        {form.medieval.chimney && (
          <Slider
            label="烟囱数量"
            value={form.medieval.chimney_count}
            min={1}
            max={4}
            step={1}
            onChange={(value) => applyMedieval({ chimney_count: value })}
          />
        )}
        <p className="hint">
          圆木墙会在转角出挑咬合；茅草屋顶仅在双坡时生效，并自动改用毛石烟囱。石瓦腰带压在坡面中段，老虎窗会嵌进腰带里；烟囱多于一座时骑屋脊分列两端。
        </p>
      </details>

      <details className="group collapsible">
        <summary>
          <h3>石屋废墟</h3>
          <span>展开</span>
        </summary>
        <div className="grid">
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.round_arch}
              disabled={medieval.collapsed || medieval.arch_openings}
              onChange={(event) => applyMedieval({ round_arch: event.target.checked })}
            />
            <span>半圆拱券</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.wall_ruin}
              onChange={(event) => applyMedieval({ wall_ruin: event.target.checked })}
            />
            <span>残墙断口</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.collapsed_beams}
              onChange={(event) => applyMedieval({ collapsed_beams: event.target.checked })}
            />
            <span>露明梁架与倒板</span>
          </label>
        </div>
        <p className="hint">
          半圆拱券把门窗改成罗曼式圆拱；残墙断口让侧墙顶部参差崩缺；露明梁架去掉了屋面板，只留破损山墙、脊梁与椽条，并在墙边斜靠木板、地上散落断板。
        </p>
      </details>

      <details className="group collapsible">
        <summary>
          <h3>哥特礼拜堂</h3>
          <span>展开</span>
        </summary>
        <div className="grid">
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.rose_window}
              onChange={(event) => applyMedieval({ rose_window: event.target.checked })}
            />
            <span>山墙玫瑰窗</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.pinnacles}
              onChange={(event) => applyMedieval({ pinnacles: event.target.checked })}
            />
            <span>扶壁小尖塔</span>
          </label>
        </div>
        <p className="hint">
          玫瑰窗嵌在前山墙正中，圆形石券外套一圈券石、内分八瓣；扶壁小尖塔立在每根扶壁顶端，山尖再加一枚石十字。
        </p>
      </details>

      <details className="group collapsible">
        <summary>
          <h3>农舍细节</h3>
          <span>展开</span>
        </summary>
        <div className="grid">
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.window_boxes}
              onChange={(event) => applyMedieval({ window_boxes: event.target.checked })}
            />
            <span>窗台花箱</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.gable_window}
              onChange={(event) => applyMedieval({ gable_window: event.target.checked })}
            />
            <span>山墙小窗</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.medieval.door_dressing}
              onChange={(event) => applyMedieval({ door_dressing: event.target.checked })}
            />
            <span>门旁花盆壁灯</span>
          </label>
        </div>
        <p className="hint">
          窗台花箱挂在首层正立面每扇窗下；山墙小窗连同花箱贴在木筋山墙正中，需要同时开启半木构与茅草顶；门旁花盆壁灯在门洞两侧摆石花盆，并在门侧点亮一盏暖光壁灯。
        </p>
      </details>

      <details className="group collapsible">
        <summary>
          <h3>中世纪街市</h3>
          <span>展开</span>
        </summary>
        <div className="medieval-grid">
          <label className="checkbox">
            <input
              type="checkbox"
              checked={medieval.slate_roof}
              disabled={!gableRoof || medieval.collapsed || medieval.thatch_roof}
              onChange={(event) => applyMedieval({ slate_roof: event.target.checked })}
            />
            <span>石板瓦曲面屋顶</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={medieval.water_wheel}
              disabled={medieval.collapsed || medieval.lookout}
              onChange={(event) => applyMedieval({ water_wheel: event.target.checked })}
            />
            <span>磨坊水车</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={medieval.shopfront}
              disabled={medieval.collapsed || medieval.stable_bays || medieval.barn_door}
              onChange={(event) => applyMedieval({ shopfront: event.target.checked })}
            />
            <span>街市橱窗</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={medieval.shop_board}
              disabled={medieval.collapsed}
              onChange={(event) => applyMedieval({ shop_board: event.target.checked })}
            />
            <span>门楣横招牌</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={medieval.stable_bays}
              disabled={medieval.collapsed || medieval.shopfront || medieval.barn_door}
              onChange={(event) => applyMedieval({ stable_bays: event.target.checked })}
            />
            <span>马厩拱形开间</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={medieval.barn_door}
              disabled={medieval.collapsed || medieval.shopfront || medieval.stable_bays}
              onChange={(event) => applyMedieval({ barn_door: event.target.checked })}
            />
            <span>谷仓大门</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={medieval.jetty_brackets}
              disabled={medieval.collapsed}
              onChange={(event) => applyMedieval({ jetty_brackets: event.target.checked })}
            />
            <span>挑楼托木</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={medieval.street_props}
              disabled={medieval.collapsed}
              onChange={(event) => applyMedieval({ street_props: event.target.checked })}
            />
            <span>街市杂物</span>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={medieval.ladder}
              disabled={medieval.collapsed}
              onChange={(event) => applyMedieval({ ladder: event.target.checked })}
            />
            <span>靠墙木梯</span>
          </label>
        </div>
        {medieval.slate_roof && (
          <Slider
            label="屋面起翘"
            value={Math.round(medieval.roof_curve * 100)}
            min={0}
            max={100}
            step={5}
            unit="%"
            onChange={(value) => applyMedieval({ roof_curve: value / 100 })}
          />
        )}
        <p className="hint">
          石板瓦曲面屋顶仅双坡可用，与厚茅草屋顶互斥；磨坊水车与瞭望棚互斥；街市橱窗 / 马厩开间 / 谷仓大门三者只能选一种；挑楼托木随悬挑楼层生效。
        </p>
      </details>

      </fieldset>
      <details className="group collapsible">
        <summary>
          <h3>门窗尺寸</h3>
          <span>展开</span>
        </summary>
        <Slider
          label="窗宽"
          value={form.openings.window_w}
          min={0.12}
          max={3.2}
          step={0.02}
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

      <div className="toggle-row">
        <label className="checkbox">
          <input
            type="checkbox"
            checked={quickPreview}
            onChange={(event) => onQuickPreviewChange(event.target.checked)}
          />
          <span>即时预览（纯前端体量）</span>
        </label>
      </div>
      <p className="hint">
        勾选后拖动参数会立即在前端拼出体量示意（毫秒级，不经过 Blender）；点「生成建筑」再生成带贴图与细节的正式模型。
      </p>

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
