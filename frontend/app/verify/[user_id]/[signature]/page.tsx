"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { GET, GRADE_RU } from "@/lib/api";
import { Card } from "@/components/ui";

function OkIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#16a34a"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <polyline points="8 12 11 15 16 9"/>
    </svg>
  );
}

function BadIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#dc2626"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <line x1="9" y1="9" x2="15" y2="15"/>
      <line x1="15" y1="9" x2="9" y2="15"/>
    </svg>
  );
}

export default function VerifyPage() {
  const { user_id, signature } = useParams<{ user_id: string; signature: string }>();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    GET(`/verify/${user_id}/${signature}`)
      .then(setData)
      .catch(() => setData({ valid: false, reason: "Проверка не найдена" }))
      .finally(() => setLoading(false));
  }, [user_id, signature]);

  return (
    <main className="min-h-screen bg-gradient-to-br from-[#3b1f5e] via-[#5e2b8e] to-[#8b5cf6] flex items-center justify-center p-6">
      <Card className="w-full max-w-md">
        <div className="flex items-center gap-2">
          {loading ? (
            <span className="h-7 w-7 rounded-full border-4 border-[#d8c9ee] border-t-[#5e2b8e]" />
          ) : data?.valid ? <OkIcon /> : <BadIcon />}
          <h1 className="text-xl font-bold text-[#3b1f5e]">
            {loading ? "Проверяем…" : data?.valid ? "Сертификат подлинный" : "Сертификат не подтверждён"}
          </h1>
        </div>

        {loading && <p className="mt-3 text-sm text-gray-500">Сверяем подпись категории на сервере…</p>}

        {!loading && data?.valid && (
          <div className="mt-4 space-y-2 text-sm">
            <p className="text-lg font-semibold text-[#1e1b4b]">{data.name}</p>
            <p className="text-gray-600">{data.specialization}</p>
            <div className="mt-3 flex items-center justify-between rounded-xl bg-[#5e2b8e]/10 px-4 py-3">
              <span className="text-[#3b1f5e]">Категория</span>
              <span className="font-semibold text-[#5e2b8e]">
                {GRADE_RU[data.grade] || data.grade}
              </span>
            </div>
            <div className="flex items-center justify-between rounded-xl bg-[#5e2b8e]/10 px-4 py-3">
              <span className="text-[#3b1f5e]">Балл</span>
              <span className="font-semibold text-[#5e2b8e]">{data.score} из 100</span>
            </div>
            <p className="mt-3 text-xs text-gray-400">
              Данные не менялись с момента выдачи — подпись HMAC-SHA256 совпала со свежей.
            </p>
          </div>
        )}

        {!loading && !data?.valid && (
          <div className="mt-4 space-y-2 text-sm">
            <p className="text-red-600">{data?.reason || "Сертификат не найден"}</p>
            <p className="text-xs text-gray-400">
              Не используйте этот сертификат для принятия решений — запросите свежий у кандидата.
            </p>
          </div>
        )}
      </Card>
    </main>
  );
}
