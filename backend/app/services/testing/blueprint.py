import random
import re
from collections import Counter
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmployerCustomItem, ItemTemplate, Specialization, TestBlueprint
from app.services.testing.scenarios import SCENARIOS

SEARCH_TIMEOUT = 6.0
KNOWLEDGE_BASE: dict[str, list[str]] = {
    "backend": ["python", "fastapi", "django", "flask", "sql", "postgresql", "mysql", "redis",
                "docker", "kafka", "kubernetes", "rest api", "git", "тестирование api", "oop",
                "асинхронность", "миграции", "кэширование", "безопасность api",
                "c++", "c#", "java", "golang", "linux"],
    "frontend": ["javascript", "typescript", "react", "vue", "next.js", "css", "html",
                 "redux", "вёрстка", "адаптивность", "а11y", "webpack", "vite", "svelte"],
    "ml": ["python", "pytorch", "tensorflow", "ml", "регуляризация", "метрики",
           "feature engineering", "mlops", "nlp", "cv", "датасеты", "a/b",
           "sklearn", "pandas", "numpy", "c++"],
    "analytics": ["sql", "python", "pandas", "метрики продукта", "a/b-тесты",
                  "визуализация", "etl", "статистика", "дашборды", "tableau",
                  "power bi", "superset"],
    "qa": ["тест-дизайн", "классы эквивалентности", "баг-репорт", "автотесты",
           "pytest", "postman", "sql", "ci/cd", "регресс", "playwright", "selenium"],
    "hr": ["трудовое право", "тк рф", "кадровое делопроизводство", "приём на работу",
           "увольнение", "отпуска", "испытательный срок", "1с:зуп", "отчётность",
           "рекрутмент", "онбординг"],
    "office_admin": ["делопроизводство", "номенклатура дел", "сэд", "регистрация документов",
                     "архивное дело", "сроки хранения", "реквизиты", "контроль исполнения",
                     "электронная подпись"],
    "devops": ["docker", "kubernetes", "ci/cd", "terraform", "мониторинг", "linux",
               "nginx", "grafana", "prometheus", "ansible", "gitlab ci", "bash"],
}


async def make_draft(
    db: AsyncSession, employer_id: str, spec_code: str, raw_text: str,
    use_web: bool = True, vacancy_id: str | None = None, code_language: str = "python",
) -> TestBlueprint:
    spec = await db.get(Specialization, spec_code)
    if spec is None:
        raise ValueError("Неизвестная специализация")


    skills = list(KNOWLEDGE_BASE.get(spec_code, []))
    web_skills, sources_used = [], []
    if use_web and skills:
        snippets: list[str] = []
        core = raw_text.strip()[:200]
        for q in (f"требования к {spec.name} навыки вакансия",
                  f"{core[:120]} ключевые навыки",
                  f"обязанности {spec.name} интервью вопросы"):
            try:
                async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT, follow_redirects=True) as client:
                    resp = await client.get(
                        "https://html.duckduckgo.com/html/",
                        params={"q": q},
                        headers={"User-Agent": "Mozilla/5.0 (compatible; FSP-Talent/0.1)"},
                    )
                if resp.status_code == 200:
                    snippets.extend(re.findall(
                        r'class="result__snippet"[^>]*>(.*?)</a>', resp.text, re.S)[:12])
            except Exception:
                pass
        if snippets:
            sources_used.append("duckduckgo")
            found: Counter = Counter()
            for snip in snippets:
                low = re.sub(r"<[^>]+>", "", snip).lower()
                for skill in set(skills):
                    if len(skill) >= 3 and re.search(rf"(?<!\w){re.escape(skill)}(?!\w)", low):
                        found[skill] += 1
            web_skills = [s for s, _ in found.most_common(15)]
    skills = list(dict.fromkeys(web_skills + skills))[:20]

    rows = (await db.execute(
        select(ItemTemplate).where(
            ItemTemplate.specialization_code == spec_code,
            ItemTemplate.is_active.is_(True),
        )
    )).scalars().all()
    rows = sorted(rows, key=lambda it: it.b)
    step = max(1, len(rows) // 10)
    bank_items = [
        {"id": str(it.id), "a": it.a, "b": it.b, "c": it.c,
         "title": it.title, "body": it.body, "template_params": it.template_params}
        for it in rows[::step][:10]
    ]

    bp = TestBlueprint(
        employer_id=employer_id,
        vacancy_id=vacancy_id,
        specialization_code=spec_code,
        title=f"Тест: {spec.name}" + (f" · {raw_text[:40]}" if raw_text else ""),
        researched_skills=skills,
        items_json=[
            {"source": "bank", "ref_id": it["id"],
             "a": it["a"], "b": it["b"], "c": it["c"],
             "title": it["title"], "body": it["body"],
             "template_params": it["template_params"]}
            for it in bank_items
        ],
        status="draft",
        code_language=code_language,
    )
    db.add(bp)
    await db.flush()
    return bp


def _autodistractors(correct: str, rng: random.Random) -> list[str]:
    """Дистракторы для своего вопроса: числа ±, даты-годы, иначе пусто."""
    t = correct.strip()
    if re.fullmatch(r"-?\d+([.,]\d+)?", t):
        try:
            base = float(t.replace(",", "."))
        except ValueError:
            return []
        outs, seen = [], {base}
        for _ in range(30):
            delta = base * rng.uniform(0.05, 0.35) * rng.choice([-1, 1])
            v = round(base + delta, 2 if isinstance(base, float) or "." in t else 0)
            if v not in seen and len(outs) < 3:
                outs.append(str(v).replace(".", ",") if "," in t else str(v))
                seen.add(v)
        return outs
    if re.fullmatch(r"(19|20)\d{2}", t):
        y = int(t)
        return [str(y + d) for d in rng.sample([-2, -1, 1, 2], 3)]
    return []


async def replace_items(db: AsyncSession, bp: TestBlueprint, items: list[dict]) -> TestBlueprint:
    bp.items_json = items
    await db.flush()
    return bp


async def add_custom_item(
    db: AsyncSession, bp: TestBlueprint, title: str, body: str,
    options: list[str], correct: str,
) -> dict:
    options = [o for o in options if o.strip()]
    if correct not in options:
        options.append(correct)
    if len(options) < 4:
        rng = random.Random()
        for d in _autodistractors(correct, rng):
            if len(options) >= 4:
                break
            options.append(d)
    custom = EmployerCustomItem(
        employer_id=bp.employer_id,
        title=title, body=body,
        options=options if len(options) >= 2 else [],
        correct=correct,
        kind="quiz" if len(options) >= 2 else "code",
    )
    db.add(custom)
    await db.flush()
    entry = {
        "source": "custom",
        "ref_id": str(custom.id),
        "a": custom.a, "b": custom.b, "c": custom.c,
        "title": title, "body": body, "options": custom.options, "correct": correct,
    }
    bp.items_json = bp.items_json + [entry]
    await db.flush()
    return entry


async def publish(db: AsyncSession, bp: TestBlueprint) -> TestBlueprint:
    bp.status = "published"
    bp.created_at = datetime.now(timezone.utc)
    await db.flush()
    return bp


def blueprint_pool(bp: TestBlueprint) -> list[dict]:
    out = []
    for entry in bp.items_json:
        if entry["source"] == "bank":
            out.append({**entry, "id": entry["ref_id"], "kind": "quiz", "is_custom": False})
        else:
            out.append({
                "id": entry["ref_id"], "kind": "quiz", "is_custom": True,
                "a": entry.get("a", 1.5), "b": entry.get("b", 0.0), "c": entry.get("c", 0.25),
                "title": entry["title"],
                "template_params": {"custom": {
                    "body": entry["body"], "options": entry.get("options", []),
                    "correct": entry["correct"],
                }},
            })
    return out
