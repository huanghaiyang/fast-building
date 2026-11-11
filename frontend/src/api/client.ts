/** 后端 API 客户端与类型定义。 */

export interface HealthInfo {
  ok: boolean;
  blender: { path: string; version: string | null };
}

export interface SocketInfo {
  name: string;
  type: string;
  pos?: number[];
  normal?: number[];
  up?: number[];
}

export interface ModuleInfo {
  id: string;
  name: string;
  category: string;
  description?: string;
  tags?: string[];
  version?: number;
  geom?: Record<string, unknown>;
  slots?: Array<{ name: string; texset?: string | null; tile_m?: number }>;
  sockets?: SocketInfo[];
  bbox?: { min: number[]; max: number[] };
  source?: { blend?: string; collection?: string };
  thumbnail?: string;
  preview?: string;
}

export interface StylePreset {
  width?: number;
  depth?: number;
  bays?: number;
  floors?: number;
  floor_height?: number;
  roof_pitch?: number;
  balcony?: boolean;
}

export interface StyleInfo {
  id: string;
  name: string;
  description?: string;
  window_w?: number;
  window_h?: number;
  sill_h?: number;
  windows_per_bay?: number;
  balcony?: boolean;
  door?: boolean;
  palette?: Record<string, string>;
  medieval?: Partial<Medieval>;
  preset?: StylePreset;
}

export interface TextureSet {
  id: string;
  name: string;
  display_name?: string;
  tile_m: number;
  resolution: number;
  preview?: string | null;
  license?: string;
  source?: string;
}

export interface Openings {
  window_w: number;
  window_h: number;
  sill_h: number;
  door_w: number;
  door_h: number;
}

export interface Medieval {
  timber_frame: boolean;
  arch_openings: boolean;
  jetty: boolean;
  crenellation: boolean;
  dormers: number;
  chimney: boolean;
  log_walls: boolean;
  thatch_roof: boolean;
  stone_plinth: boolean;
  porch: boolean;
  ivy: boolean;
  ivy_coverage: number;
  ivy_height: number;
  buttresses: boolean;
  bellcote: boolean;
  ruined_roof: boolean;
  bell_tower: boolean;
  nave_roof: boolean;
  stepped_base: boolean;
  hoarding: boolean;
  lookout: boolean;
  gallery: boolean;
  shop_sign: boolean;
  ridge_cap: boolean;
  shingle_band: boolean;
  chimney_count: number;
  collapsed: boolean;
  burnt: boolean;
}

export interface Footprint {
  width: number;
  depth: number;
  bays: number;
  floors: number;
  floor_height: number;
  roof: "flat" | "gable";
  roof_pitch: number;
  style: string;
  textureset: string;
  lod: number;
  seed: number;
  balcony: boolean;
  smooth: boolean;
  subdiv: number;
  openings: Openings;
  medieval: Medieval;
}

export interface JobStats {
  verts?: number;
  tris?: number;
  objects?: number;
  materials?: number;
  seconds?: number;
  glb_bytes?: number;
  bbox?: { min: number[]; max: number[] };
}

export interface JobView {
  id: string;
  status: "queued" | "running" | "succeeded" | "failed" | "canceled";
  stage: string;
  progress: number;
  logs: string[];
  error?: string | null;
  result: { glb?: string | null; meta?: string | null; stats?: JobStats };
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* 忽略非 JSON 错误体 */
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<HealthInfo>("/api/health"),
  modules: () => request<ModuleInfo[]>("/api/modules"),
  styles: () => request<StyleInfo[]>("/api/styles"),
  texturesets: () => request<TextureSet[]>("/api/texturesets"),
  generate: (footprint: Footprint) =>
    request<{ job_id: string }>("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(footprint),
    }),
  job: (id: string) => request<JobView>(`/api/jobs/${id}`),
  cancel: (id: string) => request<{ canceled: boolean }>(`/api/jobs/${id}/cancel`, { method: "POST" }),
  uploadTextureSet: (form: FormData) =>
    request<TextureSet>("/api/texturesets", { method: "POST", body: form }),
};
