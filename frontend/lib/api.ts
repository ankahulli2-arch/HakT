export const API = process.env.NEXT_PUBLIC_API || "http://localhost:8000/api";

const API_BASE = API;
export const photoUrl = (p?: string | null): string =>
  p ? `${API_BASE}${p.startsWith("/") ? "" : "/"}${p}` : "";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

export function getRole(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("role");
}

export function saveAuth(access: string, refresh: string, role: string) {
  localStorage.setItem("access_token", access);
  localStorage.setItem("refresh_token", refresh);
  localStorage.setItem("role", role);
}

export function logout() {
  ["access_token", "refresh_token", "role"].forEach((k) => localStorage.removeItem(k));
}

export async function api<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: res.statusText }));
    const isAuthFlow = ["/auth/login", "/auth/register", "/auth/confirm"].some((p) => path.startsWith(p));
    if (res.status === 401 && !isAuthFlow && typeof window !== "undefined") {
      logout();
      window.location.href = "/";
      throw new Error("Сессия устарела — войдите заново");
    }
    throw new Error(extractError(data));
  }
  return res.json();
}

function extractError(data: any): string {
  const d = data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    return d.map((e: any) => {
      const field = Array.isArray(e.loc) ? String(e.loc[e.loc.length - 1]) : "";
      const msg = (e.msg || "").replace(/^Value error,\s*/, "");
      return field && field !== "body" ? `${field}: ${msg}` : msg;
    }).join("; ");
  }
  return JSON.stringify(data);
}

export const GET = (path: string) => api(path);
export const POST = (path: string, body?: any, params?: Record<string, string>) =>
  api(path + (params ? "?" + new URLSearchParams(params) : ""), {
    method: "POST",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
export const PUT = (path: string, body?: any) =>
  api(path, { method: "PUT", body: body !== undefined ? JSON.stringify(body) : undefined });
export const DEL = (path: string) => api(path, { method: "DELETE" });

export async function uploadFile(path: string, file: File): Promise<any> {
  const token = getToken();
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({})))?.detail || "Ошибка загрузки");
  return res.json();
}

export const GRADE_RU: Record<string, string> = {
  junior: "младший", middle: "средний", senior: "старший", lead: "ведущий",
};
export const GRADE_RU_GEN: Record<string, string> = {
  junior: "младшего", middle: "среднего", senior: "старшего", lead: "ведущего",
};
export const NOCODE_SPECS = ["hr", "office_admin"];
export const SPEC_RU: Record<string, string> = {
  backend: "бэкенд", frontend: "фронтенд", ml: "ML", analytics: "аналитика",
  qa: "QA", hr: "HR", office_admin: "делопроизводство", devops: "DevOps",
};

async function downloadBlob(path: string, name: string) {
  const token = getToken();
  const res = await fetch(`${API}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error("Не удалось сформировать файл");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

export const downloadPdf = () => downloadBlob("/candidate/profile.pdf", "Профиль.pdf");
export const downloadCertificate = () => downloadBlob("/candidate/certificate.pdf", "Сертификат.pdf");
