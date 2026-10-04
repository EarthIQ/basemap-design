/** Join truthy class names. */
export function cn(...parts) {
  return parts.filter(Boolean).join(" ");
}

let _id = 0;
/** Tiny unique id generator for React keys / chat blocks. */
export function uid(prefix = "id") {
  _id += 1;
  return `${prefix}_${Date.now().toString(36)}_${_id}`;
}

/** Coerce a CSS colour (hex / rgb / rgba / hsl) to a #rrggbb string. */
export function toHex(v) {
  if (typeof v !== "string") return "#888888";
  if (v.startsWith("#")) {
    if (v.length === 7) return v;
    if (v.length === 4) return "#" + v[1] + v[1] + v[2] + v[2] + v[3] + v[3];
    return "#888888";
  }
  const m = v.match(/rgba?\(([^)]+)\)/);
  if (m) {
    const [r, g, b] = m[1].split(",").map((s) => parseInt(s.trim(), 10));
    return (
      "#" +
      [r, g, b].map((x) => ((x || 0).toString(16)).padStart(2, "0")).join("")
    );
  }
  return "#888888";
}

/** Compact, human-readable tool arguments for the chat timeline. */
export function shortArgs(a) {
  if (!a || Object.keys(a).length === 0) return "";
  return Object.entries(a)
    .map(([k, v]) => `${k}=${typeof v === "object" ? "…" : v}`)
    .join(" ");
}

/** Summarise a tool result into a short status line. */
export function summarizeResult(r) {
  if (!r) return "";
  if (r.ok === false) return r.error || "failed";
  if (Array.isArray(r.applied)) return `${r.applied.length} prop(s)`;
  if (r.appliedProps) return `${r.appliedProps} prop(s)`;
  if (r.loaded) return `loaded ${r.loaded}`;
  if (r.palette) return r.palette;
  if (r.added) return `added ${r.added}`;
  if (r.removed) return `removed ${r.removed}`;
  if (r.moved != null) return `moved to ${r.index}`;
  if (r.layer) return r.layer;
  if (r.background) return `bg ${r.background}`;
  return `${Object.keys(r).length} field(s)`;
}

/** Pick the most useful editable paint properties for a layer (inspector). */
export function layerPropsFor(layer) {
  const t = layer.type;
  const paint = layer.paint || {};
  const out = [];
  const add = (prop, kind) => {
    if (!out.find((x) => x.prop === prop)) out.push({ prop, kind });
  };
  if (t === "background") {
    add("background-color", "color");
  } else if (t === "fill") {
    add("fill-color", "color");
    add("fill-opacity", "number");
  } else if (t === "line") {
    add("line-color", "color");
    add("line-width", "number");
    add("line-opacity", "number");
  } else if (t === "symbol") {
    add("text-color", "color");
    add("text-halo-color", "color");
    add("text-size", "number");
    add("icon-opacity", "number");
  }
  Object.keys(paint).forEach((k) => {
    if (k.endsWith("-color") || k.endsWith("-halo-color")) add(k, "color");
    else if (typeof paint[k] === "number") add(k, "number");
  });
  return out.slice(0, 6);
}

/** Capitalise a base style / palette slug for display. */
export function titleCase(s) {
  return (s || "").replace(/[_-]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
