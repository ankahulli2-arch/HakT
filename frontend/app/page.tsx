"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { GET, POST, NOCODE_SPECS, getRole, saveAuth } from "@/lib/api";
import { Button, Card, Field, inputCls } from "@/components/ui";

export default function Landing() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [role, setRole] = useState("candidate");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [stage, setStage] = useState<"creds" | "confirm">("creds");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const r = getRole();
    if (r === "candidate") router.replace("/candidate");
    if (r === "employer") router.replace("/employer");
  }, [router]);

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      if (mode === "login") {
        const t = await POST("/auth/login", { email, password });
        saveAuth(t.access_token, t.refresh_token, t.role);
        router.replace(t.role === "employer" ? "/employer" : "/candidate");
      } else {
        const r = await POST("/auth/register", { email, password, role });
        setCode(r.confirm_code_mvp);
        setStage("confirm");
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const confirm = async () => {
    setBusy(true);
    setError("");
    try {
      const t = await POST("/auth/confirm", { email, code });
      saveAuth(t.access_token, t.refresh_token, t.role);
      router.replace(t.role === "employer" ? "/employer" : "/candidate");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-[#3b1f5e] via-[#5e2b8e] to-[#8b5cf6] flex items-center justify-center p-6">
      <div className="flex w-full max-w-6xl flex-col items-stretch justify-center gap-6 lg:flex-row">
      <Card className="w-full max-w-xl">
        <h1 className="text-xl font-bold text-[#3b1f5e]">Платформа подбора ИТ-специалистов ФСП</h1>
        <p className="mt-1 text-sm text-gray-500">
          Обратная механика: кандидат подтверждает грейд тестом, работодатель приглашает первым.
        </p>

        {stage === "creds" ? (
          <div className="mt-5 space-y-3">
            <div className="flex gap-2 text-sm">
              <button onClick={() => setMode("login")}
                className={`flex-1 rounded-xl py-2 font-medium ${mode === "login" ? "bg-[#5e2b8e] text-white" : "bg-gray-100 text-[#5e2b8e]"}`}>
                Вход
              </button>
              <button onClick={() => setMode("register")}
                className={`flex-1 rounded-xl py-2 font-medium ${mode === "register" ? "bg-[#5e2b8e] text-white" : "bg-gray-100 text-[#5e2b8e]"}`}>
                Регистрация
              </button>
            </div>
            {mode === "register" && (
              <Field label="Кто вы?">
                <div className="grid grid-cols-2 gap-2">
                  <button onClick={() => setRole("candidate")}
                    className={`rounded-xl border-2 p-3 text-left transition ${role === "candidate" ? "border-[#5e2b8e] bg-[#5e2b8e]/10" : "border-gray-200 hover:border-[#d8c9ee]"}`}>
                    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#5e2b8e" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="16 18 22 12 16 6"/>
                      <polyline points="8 6 2 12 8 18"/>
                    </svg>
                    <p className="mt-1 text-sm font-semibold text-[#3b1f5e]">Кандидат</p>
                    <p className="text-xs text-gray-500">Ищу работу в ИТ</p>
                  </button>
                  <button onClick={() => setRole("employer")}
                    className={`rounded-xl border-2 p-3 text-left transition ${role === "employer" ? "border-[#5e2b8e] bg-[#5e2b8e]/10" : "border-gray-200 hover:border-[#d8c9ee]"}`}>
                    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#5e2b8e" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="4" y="3" width="16" height="18" rx="1"/>
                      <line x1="9" y1="8" x2="10" y2="8"/><line x1="14" y1="8" x2="15" y2="8"/>
                      <line x1="9" y1="12" x2="10" y2="12"/><line x1="14" y1="12" x2="15" y2="12"/>
                      <rect x="10" y="16" width="4" height="5"/>
                    </svg>
                    <p className="mt-1 text-sm font-semibold text-[#3b1f5e]">Работодатель</p>
                    <p className="text-xs text-gray-500">Ищу специалистов</p>
                  </button>
                </div>
              </Field>
            )}
            <Field label="Email">
              <input className={inputCls} value={email} onChange={(e) => setEmail(e.target.value)} type="email" />
            </Field>
            <Field label="Пароль">
              <input className={inputCls} value={password} onChange={(e) => setPassword(e.target.value)} type="password" />
            </Field>
            {mode === "register" && (
              <p className="text-xs text-gray-500">
                Пароль: от 8 символов, заглавная и строчная буквы, цифра или спецсимвол
              </p>
            )}
            <Button onClick={submit} disabled={busy || !email || !password} className="w-full">
              {busy ? "…" : mode === "login" ? "Войти" : "Зарегистрироваться"}
            </Button>
          </div>
        ) : (
          <div className="mt-5 space-y-3">
            <p className="text-sm text-gray-600">
              Код подтверждения отправлен на {email}. (MVP: код — <b>{code}</b>)
            </p>
            <Field label="Код из письма">
              <input className={inputCls} value={code} onChange={(e) => setCode(e.target.value)} maxLength={6} />
            </Field>
            <Button onClick={confirm} disabled={busy || code.length !== 6} className="w-full">
              {busy ? "…" : "Подтвердить"}
            </Button>
          </div>
        )}

        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </Card>
      <DemoQuiz onRegister={() => setMode("register")} />
      </div>
    </main>
  );
}

function DemoQuiz({ onRegister }: { onRegister: () => void }) {
  const [phase, setPhase] = useState<"idle" | "playing" | "done">("idle");
  const [token, setToken] = useState("");
  const [item, setItem] = useState<any>(null);
  const [theta, setTheta] = useState(0);
  const [asked, setAsked] = useState(0);
  const [verdict, setVerdict] = useState<{ correct: boolean; answer: any } | null>(null);
  const [score, setScore] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [specs, setSpecs] = useState<any[]>([]);
  const [spec, setSpec] = useState("backend");
  const [lang, setLang] = useState("python");

  useEffect(() => {
    GET("/testing/specializations").then((r: any) => setSpecs(r || [])).catch(() => {});
  }, []);

  const start = async () => {
    setBusy(true);
    setError("");
    try {
      const r = await POST("/demo/quiz/start", undefined,
        NOCODE_SPECS.includes(spec) ? { spec } : { spec, language: lang });
      setToken(r.token);
      setItem(r.item);
      setPhase("playing");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const answer = async (body: any) => {
    if (busy || verdict) return;
    setBusy(true);
    setError("");
    try {
      const a = await POST("/demo/quiz/answer", { token, item_id: item.id, ...body });
      setVerdict({ correct: a.correct, answer: a.answer });
      setTheta(a.theta);
      setAsked((n) => n + 1);
      if (a.finished) {
        setScore(a.score);
        setTimeout(() => setPhase("done"), 900);
      } else {
        setTimeout(() => { setItem(a.next_item); setVerdict(null); setDraft(""); }, 1100);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    setPhase("idle");
    setItem(null);
    setVerdict(null);
    setScore(null);
    setAsked(0);
    setTheta(0);
  };

  return (
    <Card className="w-full max-w-xl">
      <h2 className="text-lg font-bold text-[#3b1f5e]">Попробуйте CAT-тест прямо сейчас</h2>
      <p className="mt-1 text-sm text-gray-500">
        3 задания без регистрации. Сложность подбирается под ваш уровень после каждого ответа —
        так же устроен настоящий тест для присвоения категории.
      </p>

      {phase === "idle" && (
        <div className="mt-4 space-y-3">
          <div className={`grid gap-2 ${NOCODE_SPECS.includes(spec) ? "grid-cols-1" : "grid-cols-2"}`}>
            <Field label="Специальность">
              <select className={inputCls} value={spec} onChange={(e) => setSpec(e.target.value)}>
                {(specs.length > 0 ? specs : [{ code: "backend", name: "Бэкенд-разработчик" }])
                  .map((s: any) => <option key={s.code} value={s.code}>{s.name}</option>)}
              </select>
            </Field>
            {!NOCODE_SPECS.includes(spec) && (
              <Field label="Язык заданий">
                <select className={inputCls} value={lang} onChange={(e) => setLang(e.target.value)}>
                  {[["python", "Python"], ["javascript", "JavaScript"], ["c++", "C++"],
                    ["c#", "C#"], ["java", "Java"]]
                    .map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </Field>
            )}
          </div>
          <Button onClick={start} disabled={busy} className="w-full">
            {busy ? "…" : "Начать демо — 3 задания"}
          </Button>
          <div className="grid grid-cols-3 gap-2 text-center text-xs text-gray-500">
            <div className="rounded-lg bg-gray-50 p-2"><b className="block text-[#5e2b8e]">Адаптивность</b>сервер выбирает задания по вашей способности θ</div>
            <div className="rounded-lg bg-gray-50 p-2"><b className="block text-[#5e2b8e]">Item Response</b>модель 3PL: сложность и различительная сила</div>
            <div className="rounded-lg bg-gray-50 p-2"><b className="block text-[#5e2b8e]">Оценка EAP</b>байесовская оценка θ после каждого ответа</div>
          </div>
        </div>
      )}

      {phase === "playing" && item && (
        <div className="mt-4 space-y-3">
          <div className="flex items-center justify-between text-xs text-gray-500">
            <span>Задание {Math.min(asked + 1, 3)} из 3</span>
            <span>оценка θ ≈ {theta.toFixed(2)}</span>
          </div>
          <div className="rounded-xl bg-gray-50 p-3">
            <p className="text-sm font-medium text-[#3b1f5e]">{item.title}</p>
            <pre className="mt-2 overflow-x-auto whitespace-pre-wrap font-mono text-xs text-gray-700">{item.body}</pre>
          </div>
          {item.answer_type === "choice" ? (
            <div className="grid gap-2">
              {(item.options || []).map((op: string, i: number) => (
                <button key={i} onClick={() => answer({ choice: i })}
                  className={`rounded-xl border-2 px-3 py-2 text-left text-sm transition ${
                    verdict && verdict.answer === i
                      ? "border-green-500 bg-green-50"
                      : "border-gray-200 hover:border-[#5e2b8e]"}`}>
                  {op}
                </button>
              ))}
            </div>
          ) : (
            <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); answer({ value: draft }); }}>
              <input className={inputCls} value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Ваш ответ" />
              <Button type="submit" disabled={busy || !draft}>OK</Button>
            </form>
          )}
          {verdict && (
            <p className={`text-sm font-medium ${verdict.correct ? "text-green-600" : "text-red-600"}`}>
              {verdict.correct
                ? "Верно — сложность следующего задания выше"
                : `Неверно. Правильный ответ: ${
                    item.answer_type === "choice" ? (item.options || [])[verdict.answer] : verdict.answer
                  } — подбираем попроще`}
            </p>
          )}
        </div>
      )}

      {phase === "done" && (
        <div className="mt-4 space-y-3 text-center">
          <p className="text-4xl font-bold text-[#5e2b8e]">{score} из 100</p>
          <p className="text-sm text-gray-600">
            Ваша предварительная оценка θ ≈ {theta.toFixed(2)}. Чтобы получить официальную категорию,
            пройдите полный тест — он займёт 10–15 минут.
          </p>
          <div className="flex gap-2">
            <Button onClick={onRegister} className="flex-1">Зарегистрироваться</Button>
            <Button variant="ghost" onClick={reset}>Ещё раз</Button>
          </div>
        </div>
      )}

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
    </Card>
  );
}
