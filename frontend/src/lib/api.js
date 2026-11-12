import axios from "axios";

export const BACKEND = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
export const api = axios.create({ baseURL: `${BACKEND}/api` });

api.interceptors.request.use((cfg) => {
  const t = localStorage.getItem("onx_token");
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401 && localStorage.getItem("onx_token") && !err.config.url.includes("/auth/login")) {
      localStorage.removeItem("onx_token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export function errMsg(e) {
  const d = e?.response?.data?.detail;
  if (!d) return e?.message || "Something went wrong";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x?.msg || JSON.stringify(x)).join(" ");
  return d.msg || String(d);
}

export async function streamSSE(path, body, onEvent) {
  const res = await fetch(`${BACKEND}/api${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("onx_token")}` },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const j = await res.json().catch(() => ({}));
    throw new Error(typeof j.detail === "string" ? j.detail : `Request failed (${res.status})`);
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop();
    for (const p of parts) {
      const line = p.split("\n").find((l) => l.startsWith("data: "));
      if (line) onEvent(JSON.parse(line.slice(6)));
    }
  }
}

export function citation(p) {
  const a = p.authors || [];
  const au = a.length === 0 ? "Unknown author" : a.length > 3 ? `${a.slice(0, 3).join(", ")}, et al.` : a.join(", ");
  return `${au} (${p.year || "n.d."}). ${p.title}.${p.journal ? ` ${p.journal}.` : ""}${p.doi ? ` https://doi.org/${p.doi}` : p.url ? ` ${p.url}` : ""}`;
}
