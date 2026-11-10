import { useMemo, useState } from "react";
import { ModuleInfo } from "../api/client";
import { ModulePreview } from "../viewer/ModulePreview";

const CATEGORY_LABELS: Record<string, string> = {
  wall: "墙体",
  slab: "楼板",
  roof: "屋顶",
  opening: "门窗",
  stair: "楼梯",
  balcony: "阳台",
};

const CATEGORY_ORDER = ["all", "wall", "slab", "roof", "opening", "stair", "balcony"];

interface Props {
  modules: ModuleInfo[];
}

/** 左侧模块库：分类筛选 + 模块卡片 + 拆解规范说明。 */
export function ModuleLibrary({ modules }: Props) {
  const [category, setCategory] = useState("all");
  const [expanded, setExpanded] = useState<string | null>(null);

  const counts = useMemo(() => {
    const result: Record<string, number> = { all: modules.length };
    for (const module of modules) {
      result[module.category] = (result[module.category] ?? 0) + 1;
    }
    return result;
  }, [modules]);

  const visible = category === "all" ? modules : modules.filter((item) => item.category === category);

  return (
    <div className="panel-inner">
      <div className="panel-head">
        <div>
          <h2>模块库</h2>
          <p className="panel-sub">缩略图预览 · 点击展开三维模型</p>
        </div>
        <span className="count-badge">{modules.length}</span>
      </div>

      <div className="tabs">
        {CATEGORY_ORDER.map((key) => (
          <button
            key={key}
            type="button"
            className={`tab ${category === key ? "active" : ""}`}
            onClick={() => setCategory(key)}
          >
            {key === "all" ? "全部" : CATEGORY_LABELS[key] ?? key}
            <span>{counts[key] ?? 0}</span>
          </button>
        ))}
      </div>

      <div className="module-list">
        {visible.map((module) => {
          const isOpen = expanded === module.id;
          return (
            <article
              key={module.id}
              className={`module-card ${isOpen ? "open" : ""}`}
              onClick={() => setExpanded(isOpen ? null : module.id)}
            >
              <div className="module-card-top">
                <span className="module-thumb">
                  {module.thumbnail && (
                    <img
                      src={module.thumbnail}
                      alt={module.name}
                      loading="lazy"
                      onError={(event) => {
                        event.currentTarget.style.display = "none";
                      }}
                    />
                  )}
                </span>
                <div className="module-title">
                  <h3>
                    <span className={`category-dot cat-${module.category}`} />
                    {module.name}
                  </h3>
                  <p>{module.description}</p>
                </div>
                <span className="module-cat">{CATEGORY_LABELS[module.category] ?? module.category}</span>
              </div>

              <div className="module-tags">
                {(module.tags ?? []).map((tag) => (
                  <span key={tag} className="tag">
                    {tag}
                  </span>
                ))}
              </div>

              {isOpen && (
                <div className="module-detail">
                  <div onClick={(event) => event.stopPropagation()}>
                    <ModulePreview moduleId={module.id} />
                  </div>
                  <div className="detail-row">
                    <span>几何类型</span>
                    <code>{String(module.geom?.type ?? "-")}</code>
                  </div>
                  <div className="detail-row">
                    <span>插槽</span>
                    <code>{module.slots?.map((slot) => slot.name).join(" / ") || "-"}</code>
                  </div>
                  <div className="detail-row">
                    <span>接口</span>
                    <code>{module.sockets?.map((socket) => `${socket.name}:${socket.type}`).join(" / ") || "-"}</code>
                  </div>
                  <div className="detail-row">
                    <span>集合</span>
                    <code>{module.source?.collection ?? "-"}</code>
                  </div>
                </div>
              )}
            </article>
          );
        })}
        {visible.length === 0 && <p className="empty-hint">该分类下暂无模块。</p>}
      </div>

      <div className="spec-block">
        <h3>拆解规范</h3>
        <ul>
          <li>
            集合命名 <code>MOD_&lt;category&gt;_&lt;name&gt;</code>，一个集合即一个可复用模块。
          </li>
          <li>
            空物体 <code>SOCK_&lt;type&gt;_&lt;name&gt;</code> 定义接口，本地 <code>-Y</code> 为法线、<code>+Z</code> 为上。
          </li>
          <li>
            对象自定义属性 <code>slot</code> 与 <code>tile_m</code> 决定材质槽和贴图密度。
          </li>
          <li>同名模块追加 <code>_L0 / _L1</code> 后缀归入同一模块的 LOD 层级。</li>
        </ul>
      </div>
    </div>
  );
}
