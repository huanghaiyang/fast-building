import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  Footprint,
  HealthInfo,
  JobView,
  Medieval,
  ModuleInfo,
  Openings,
  StyleInfo,
  TextureSet,
} from "./api/client";
import { ModuleLibrary } from "./panels/ModuleLibrary";
import { ControlPanel } from "./panels/ControlPanel";
import { UploadDialog } from "./panels/UploadDialog";
import { ViewerStage } from "./viewer/ViewerStage";

const DEFAULT_FORM: Footprint = {
  width: 12,
  depth: 9,
  bays: 3,
  floors: 3,
  floor_height: 3,
  roof: "gable",
  roof_pitch: 30,
  style: "modern_villa",
  textureset: "brick_red",
  lod: 0,
  seed: 42,
  balcony: true,
  openings: {
    window_w: 1.4,
    window_h: 1.6,
    sill_h: 0.9,
    door_w: 1.05,
    door_h: 2.2,
  },
  medieval: {
    timber_frame: false,
    arch_openings: false,
    jetty: false,
    crenellation: false,
    dormers: 0,
    chimney: false,
    log_walls: false,
    thatch_roof: false,
    stone_plinth: false,
    porch: false,
  },
};

export default function App() {
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [modules, setModules] = useState<ModuleInfo[]>([]);
  const [styles, setStyles] = useState<StyleInfo[]>([]);
  const [textureSets, setTextureSets] = useState<TextureSet[]>([]);
  const [form, setForm] = useState<Footprint>(DEFAULT_FORM);
  const [job, setJob] = useState<JobView | null>(null);
  const [glbUrl, setGlbUrl] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const pollRef = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [healthInfo, moduleList, styleList, setList] = await Promise.all([
          api.health(),
          api.modules(),
          api.styles(),
          api.texturesets(),
        ]);
        if (cancelled) return;
        setHealth(healthInfo);
        setModules(moduleList);
        setStyles(styleList);
        setTextureSets(setList);
        setForm((current) => {
          const next = { ...current };
          if (styleList.length && !styleList.some((item) => item.id === current.style)) {
            next.style = styleList[0].id;
          }
          if (setList.length && !setList.some((item) => item.id === current.textureset)) {
            next.textureset = setList[0].id;
          }
          return next;
        });
      } catch (err) {
        if (!cancelled) {
          setHealth({ ok: false, blender: { path: "", version: null } });
          setError(`无法连接后端服务：${err instanceof Error ? err.message : String(err)}`);
        }
      }
    })();
    return () => {
      cancelled = true;
      stopPolling();
    };
  }, [stopPolling]);

  const poll = useCallback(
    (jobId: string) => {
      stopPolling();
      let failures = 0;
      const tick = async () => {
        try {
          const current = await api.job(jobId);
          setJob(current);
          failures = 0;
          if (current.status === "succeeded") {
            stopPolling();
            setSubmitting(false);
            if (current.result.glb) {
              setGlbUrl(`${current.result.glb}?v=${Date.now()}`);
            }
          } else if (current.status === "failed" || current.status === "canceled") {
            stopPolling();
            setSubmitting(false);
          }
        } catch (err) {
          failures += 1;
          if (failures >= 3) {
            stopPolling();
            setSubmitting(false);
            setError(`任务状态查询失败：${err instanceof Error ? err.message : String(err)}`);
          }
        }
      };
      void tick();
      pollRef.current = window.setInterval(tick, 800);
    },
    [stopPolling],
  );

  const handleGenerate = useCallback(async () => {
    if (!health?.ok) {
      setError("后端未就绪或未找到 Blender，请检查服务状态。");
      return;
    }
    setError(null);
    setGlbUrl(null);
    setJob(null);
    setSubmitting(true);
    try {
      const response = await api.generate(form);
      poll(response.job_id);
    } catch (err) {
      setSubmitting(false);
      setError(`提交任务失败：${err instanceof Error ? err.message : String(err)}`);
    }
  }, [form, health, poll]);

  const handleCancel = useCallback(async () => {
    if (!job) return;
    try {
      await api.cancel(job.id);
    } catch (err) {
      setError(`取消失败：${err instanceof Error ? err.message : String(err)}`);
    }
  }, [job]);

  const handleUploaded = useCallback(async (textureSet: TextureSet) => {
    setUploadOpen(false);
    try {
      const list = await api.texturesets();
      setTextureSets(list);
    } catch {
      setTextureSets((current) => [...current, textureSet]);
    }
    setForm((current) => ({ ...current, textureset: textureSet.id }));
  }, []);

  const handleChange = useCallback(
    (patch: Partial<Footprint>) => {
      setForm((current) => {
        const next = { ...current, ...patch };
        if (patch.style && patch.style !== current.style) {
          const style = styles.find((item) => item.id === patch.style);
          const preset = style?.medieval;
          if (preset) {
            next.medieval = {
              timber_frame: preset.timber_frame ?? current.medieval.timber_frame,
              arch_openings: preset.arch_openings ?? current.medieval.arch_openings,
              jetty: preset.jetty ?? current.medieval.jetty,
              crenellation: preset.crenellation ?? current.medieval.crenellation,
              dormers: preset.dormers ?? current.medieval.dormers,
              chimney: preset.chimney ?? current.medieval.chimney,
              log_walls: preset.log_walls ?? current.medieval.log_walls,
              thatch_roof: preset.thatch_roof ?? current.medieval.thatch_roof,
              stone_plinth: preset.stone_plinth ?? current.medieval.stone_plinth,
              porch: preset.porch ?? current.medieval.porch,
            };
          }
          // 风格自带的体量预设（例如茅草农舍默认单层小体量）
          const geometry = style?.preset;
          if (geometry) {
            next.width = geometry.width ?? next.width;
            next.depth = geometry.depth ?? next.depth;
            next.bays = geometry.bays ?? next.bays;
            next.floors = geometry.floors ?? next.floors;
            next.floor_height = geometry.floor_height ?? next.floor_height;
            next.roof_pitch = geometry.roof_pitch ?? next.roof_pitch;
            next.balcony = geometry.balcony ?? next.balcony;
            next.medieval.jetty = false;
            next.medieval.dormers = 0;
          }
        }
        return next;
      });
    },
    [styles],
  );

  const handleMedievalChange = useCallback((patch: Partial<Medieval>) => {
    setForm((current) => ({
      ...current,
      medieval: { ...current.medieval, ...patch },
    }));
  }, []);

  const busy = submitting || job?.status === "queued" || job?.status === "running";

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">FB</span>
          <div>
            <h1>快速构建建筑平台</h1>
            <p>模块拆解 · 参数化重组 · 本机 Blender 构建</p>
          </div>
        </div>
        <div className="topbar-right">
          <span className={`health ${health?.ok ? "ok" : "bad"}`}>
            <i />
            {health
              ? health.ok
                ? health.blender.version ?? "Blender 就绪"
                : "Blender 未找到"
              : "连接后端..."}
          </span>
          <span className="build-tag">MVP 0.1</span>
        </div>
      </header>

      <main className="workspace">
        <aside className="panel left">
          <ModuleLibrary modules={modules} />
        </aside>

        <ViewerStage url={glbUrl} />

        <aside className="panel right">
          <ControlPanel
            form={form}
            onChange={handleChange}
            onOpeningsChange={(patch: Partial<Openings>) =>
              setForm((current) => ({ ...current, openings: { ...current.openings, ...patch } }))
            }
            onMedievalChange={handleMedievalChange}
            styles={styles}
            textureSets={textureSets}
            job={job}
            busy={busy}
            glbUrl={glbUrl}
            error={error}
            onGenerate={handleGenerate}
            onCancel={handleCancel}
            onOpenUpload={() => setUploadOpen(true)}
          />
        </aside>
      </main>

      {uploadOpen && (
        <UploadDialog onClose={() => setUploadOpen(false)} onUploaded={handleUploaded} />
      )}
    </div>
  );
}
