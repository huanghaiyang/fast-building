import { FormEvent, useState } from "react";
import { api, TextureSet } from "../api/client";

const CHANNELS: Array<{ key: string; label: string; hint: string }> = [
  { key: "basecolor", label: "Base Color", hint: "基础色（sRGB）" },
  { key: "normal", label: "Normal", hint: "法线图" },
  { key: "roughness", label: "Roughness", hint: "粗糙度" },
  { key: "metallic", label: "Metallic", hint: "金属度" },
  { key: "ao", label: "AO", hint: "环境光遮蔽" },
  { key: "height", label: "Height", hint: "高度图（可选，仅存档）" },
];

interface Props {
  onClose: () => void;
  onUploaded: (textureSet: TextureSet) => void;
}

/** PBR 贴图集导入弹窗：后端会自动统一尺寸并打包 ORM。 */
export function UploadDialog({ onClose, onUploaded }: Props) {
  const [name, setName] = useState("");
  const [tileM, setTileM] = useState(2);
  const [license, setLicense] = useState("");
  const [source, setSource] = useState("");
  const [files, setFiles] = useState<Record<string, File | null>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasFile = Object.values(files).some(Boolean);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim() || !hasFile) {
      setError("请填写名称并至少上传一个通道贴图");
      return;
    }
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.append("name", name.trim());
    form.append("tile_m", String(tileM));
    form.append("license_text", license);
    form.append("source", source);
    for (const channel of CHANNELS) {
      const file = files[channel.key];
      if (file) form.append(channel.key, file);
    }
    try {
      const meta = await api.uploadTextureSet(form);
      onUploaded(meta);
    } catch (err) {
      setError(err instanceof Error ? err.message : "上传失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <form className="modal" onClick={(event) => event.stopPropagation()} onSubmit={handleSubmit}>
        <header className="modal-head">
          <div>
            <h2>导入 PBR 贴图集</h2>
            <p>通道图会被统一为 2 的幂方形并自动打包 ORM（R=AO / G=Roughness / B=Metallic）。</p>
          </div>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="关闭">
            ×
          </button>
        </header>

        <div className="modal-grid">
          <label className="field">
            <span className="field-label">贴图集名称</span>
            <input
              type="text"
              placeholder="例如 red_brick_a"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <label className="field">
            <span className="field-label">贴图密度（tile_m）</span>
            <input
              type="number"
              min={0.1}
              max={20}
              step={0.1}
              value={tileM}
              onChange={(event) => setTileM(Number(event.target.value))}
            />
          </label>
        </div>

        <div className="channel-grid">
          {CHANNELS.map((channel) => (
            <label key={channel.key} className="channel">
              <span>{channel.label}</span>
              <small>{channel.hint}</small>
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                onChange={(event) =>
                  setFiles((current) => ({
                    ...current,
                    [channel.key]: event.target.files?.[0] ?? null,
                  }))
                }
              />
            </label>
          ))}
        </div>

        <div className="modal-grid">
          <label className="field">
            <span className="field-label">版权信息</span>
            <input
              type="text"
              placeholder="例如 CC0 / 自购授权"
              value={license}
              onChange={(event) => setLicense(event.target.value)}
            />
          </label>
          <label className="field">
            <span className="field-label">来源</span>
            <input
              type="text"
              placeholder="来源站点或作者"
              value={source}
              onChange={(event) => setSource(event.target.value)}
            />
          </label>
        </div>

        {error && <div className="alert">{error}</div>}

        <footer className="modal-foot">
          <button type="button" className="btn ghost" onClick={onClose}>
            取消
          </button>
          <button type="submit" className="btn primary" disabled={busy}>
            {busy ? "处理中..." : "上传并生成贴图集"}
          </button>
        </footer>
      </form>
    </div>
  );
}
