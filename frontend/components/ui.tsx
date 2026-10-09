"use client";

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl bg-white shadow-sm p-5 ${className}`}>{children}</div>
  );
}

export function Button({
  children, onClick, variant = "primary", disabled, type = "button", className = "",
}: {
  children: React.ReactNode; onClick?: () => void;
  variant?: "primary" | "ghost" | "danger" | "white"; disabled?: boolean;
  type?: "button" | "submit"; className?: string;
}) {
  const styles = {
    primary: "bg-[#5e2b8e] text-white hover:bg-[#4a2172]",
    ghost: "bg-transparent text-[#5e2b8e] border border-[#5e2b8e] hover:bg-[#5e2b8e]/10",
    danger: "bg-white text-red-600 border border-red-300 hover:bg-red-50",
    white: "bg-white text-[#5e2b8e] shadow hover:bg-[#f1e8fb]",
  }[variant];
  return (
    <button type={type} onClick={onClick} disabled={disabled}
      className={`px-4 py-2 rounded-xl font-medium transition disabled:opacity-50 ${styles} ${className}`}>
      {children}
    </button>
  );
}

export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="text-[#5e2b8e] font-medium">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}

export const inputCls =
  "w-full rounded-xl border border-[#d8c9ee] bg-white px-3 py-2 text-sm text-[#1e1b4b] " +
  "placeholder:text-gray-400 outline-none focus:border-[#5e2b8e] focus:ring-1 focus:ring-[#5e2b8e]";

export function Badge({ children, tone = "purple" }: { children: React.ReactNode; tone?: "purple" | "green" | "gray" }) {
  const styles = {
    purple: "bg-[#5e2b8e] text-white",
    green: "bg-emerald-500 text-white",
    gray: "bg-gray-200 text-gray-700",
  }[tone];
  return <span className={`inline-block rounded-full px-3 py-1 text-xs font-semibold ${styles}`}>{children}</span>;
}

export function Bar({ value, label }: { value: number; label: string }) {
  return (
    <div className="text-xs">
      <div className="flex justify-between text-gray-600">
        <span>{label}</span>
        <span>{Math.round(value * 100)}%</span>
      </div>
      <div className="mt-0.5 h-1.5 rounded-full bg-gray-100">
        <div className="h-1.5 rounded-full bg-[#5e2b8e]" style={{ width: `${value * 100}%` }} />
      </div>
    </div>
  );
}


export function Sparkline({ values, w = 160, h = 44 }: { values: number[]; w?: number; h?: number }) {
  if (values.length < 2) {
    return <span className="text-xs text-gray-400">одна попытка — график появится со второй</span>;
  }
  const min = Math.min(...values), max = Math.max(...values);
  const pts = values.map((v, i) =>
    `${(i / (values.length - 1)) * (w - 8) + 4},${h - 6 - ((v - min) / ((max - min) || 1)) * (h - 12)}`
  ).join(" ");
  return (
    <svg width={w} height={h} className="shrink-0">
      <polyline points={pts} fill="none" stroke="#5e2b8e" strokeWidth="2.5" strokeLinejoin="round" />
      {values.map((v, i) => (
        <circle key={i} cx={(i / (values.length - 1)) * (w - 8) + 4}
          cy={h - 6 - ((v - min) / ((max - min) || 1)) * (h - 12)} r="3" fill="#5e2b8e" />
      ))}
    </svg>
  );
}

export const GRADE_TITLE: Record<string, string> = {
  junior: "Джун", middle: "Мидл", senior: "Сеньор", lead: "Лид",
};

export function ruCategory(cat?: string | null): string {
  if (!cat) return "";
  const [spec, grade] = cat.split(" · ");
  return grade ? `${spec} · ${GRADE_TITLE[grade] || grade}` : cat;
}

const FSP_KIND_RU: Record<string, string> = {
  tournament: "Турнир", olympiad: "Олимпиада", event: "Мероприятие",
};
const FSP_LEVEL_RU: Record<string, string> = {
  international: "международный", national: "национальный", regional: "региональный",
};

export function FspAchievements({ items }: { items: any[] }) {
  return (
    <div className="mt-2 space-y-1.5 text-sm">
      {(items || []).map((a: any, i: number) => (
        <div key={i} className="flex flex-wrap items-center gap-2 rounded-xl bg-gray-50 px-3 py-1.5">
          <Badge tone="gray">{FSP_KIND_RU[a.kind] || a.kind}</Badge>
          <span className="text-[#1e1b4b]">{a.title}</span>
          <span className="text-xs text-gray-500">
            {FSP_LEVEL_RU[a.level] || a.level} · {a.result} · {a.year}
          </span>
        </div>
      ))}
    </div>
  );
}

export function HistoryBlock({ history }: any) {
  return (
    <div className="space-y-3">
      {history.map((g: any) => (
        <div key={g.specialization} className="rounded-xl bg-gray-50 p-3">
          <div className="flex items-center justify-between">
            <b className="text-sm text-[#3b1f5e]">{g.specialization}</b>
            <Badge>лучший балл {g.best_score} из 100</Badge>
          </div>
          <div className="mt-1 flex items-center gap-3">
            <Sparkline values={g.attempts.map((a: any) => a.theta)} />
            <div className="text-xs text-gray-600">
              {g.attempts.map((a: any, i: number) => (
                <p key={i}>{a.date} · балл {a.score} из 100 · {a.grade} · честность {Math.round(a.integrity * 100)}%</p>
              ))}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
