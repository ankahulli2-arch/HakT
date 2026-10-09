import math
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GRADE_ORDER, CandidateCategory, CandidateProfile, EmployerNeed, Grade

WEIGHTS = {
    "theta": 0.45,
    "fsp": 0.20,
    "freshness": 0.15,
    "match": 0.10,
    "reliability": 0.10,
}
LEVEL_WEIGHT = {"international": 1.0, "national": 0.7, "regional": 0.4}
YEAR_DECAY = 0.85

GRADE_RU = {"junior": "младший", "middle": "средний", "senior": "старший", "lead": "ведущий"}
breakdown_order = ["theta", "fsp", "freshness", "match", "reliability"]


def category_ru(spec_name: str, grade: str) -> str:
    return f"{spec_name} · {GRADE_RU[grade]}"


def theta_to_grade(theta: float) -> str:
    bounds = [-0.5, 0.5, 1.5]
    return next((GRADE_ORDER[i] for i, b in enumerate(bounds) if theta < b), "lead")


def theta_to_score(theta: float) -> int:
    """Понятный балл 0–100 из θ (пользовательский язык вместо «θ = -1.95»)."""
    return int(round(100.0 / (1.0 + math.exp(-theta))))


def fsp_index(history: list | None) -> float:
    if not history:
        return 0.0
    now_year = datetime.now(timezone.utc).year
    total = sum(
        LEVEL_WEIGHT.get(a.get("level"), 0.3)
        * YEAR_DECAY ** max(0, now_year - int(a.get("year", now_year)))
        for a in history
    )
    return min(1.0, total * 0.25)


def compute_score(
    candidate: CandidateProfile, need_stack: list, solved_recent: bool = False,
    theta_override: float | None = None, need_vec: list | None = None,
) -> tuple[float, dict]:
    theta_value = 1.0 / (1.0 + math.exp(-(theta_override if theta_override is not None else (candidate.theta or 0.0))))

    fsp_value = fsp_index(candidate.fsp_history)

    if candidate.last_activity_at is None:
        fresh_value = 0.5
    else:
        days = max(0.0, (datetime.now(timezone.utc) - candidate.last_activity_at).total_seconds() / 86400)
        fresh_value = min(1.0, math.exp(-days / 21.0) + (0.25 if solved_recent else 0.0))

    if candidate.stack and need_stack:
        cs = {s.lower().strip() for s in candidate.stack}
        ns = {s.lower().strip() for s in need_stack}
        match_value = len(cs & ns) / len(ns) if ns else 0.5
    else:
        match_value = 0.5
    doc = " ".join(candidate.stack or []) + " " + (candidate.summary or "")
    need_v = need_vec if need_vec is not None else text_vector(" ".join(need_stack or []))
    match_value = max(match_value, round(match_semantic(doc, need_v), 3))

    if candidate.theta_se is None:
        rel_value = 0.5
    else:
        rel_value = 1.0 / (1.0 + candidate.theta_se**2)
        if candidate.theta_history and len(candidate.theta_history) > 1:
            mean = sum(candidate.theta_history) / len(candidate.theta_history)
            var = sum((t - mean) ** 2 for t in candidate.theta_history) / len(candidate.theta_history)
            rel_value = 0.5 * rel_value + 0.5 * (1.0 / (1.0 + var))
    rel_value *= 0.6 + 0.4 * (candidate.integrity if candidate.integrity is not None else 1.0)

    breakdown = {
        "theta": {"value": round(theta_value, 3), "weight": WEIGHTS["theta"],
                  "contribution": round(WEIGHTS["theta"] * theta_value, 3),
                  "label": "Тестовая способность (θ, IRT)"},
        "fsp": {"value": round(fsp_value, 3), "weight": WEIGHTS["fsp"],
                "contribution": round(WEIGHTS["fsp"] * fsp_value, 3),
                "label": "Достижения ФСП"},
        "freshness": {"value": round(fresh_value, 3), "weight": WEIGHTS["freshness"],
                      "contribution": round(WEIGHTS["freshness"] * fresh_value, 3),
                      "label": "Активность профиля"},
        "match": {"value": round(match_value, 3), "weight": WEIGHTS["match"],
                  "contribution": round(WEIGHTS["match"] * match_value, 3),
                  "label": "Соответствие стеку"},
        "reliability": {"value": round(rel_value, 3), "weight": WEIGHTS["reliability"],
                        "contribution": round(WEIGHTS["reliability"] * rel_value, 3),
                        "label": "Стабильность результатов"},
    }
    return sum(v["contribution"] for v in breakdown.values()), breakdown


async def parse_need(db: AsyncSession, raw_text: str) -> dict:
    from app.models import Specialization
    specs = (await db.execute(select(Specialization))).scalars().all()

    text = raw_text.lower()
    spec_code = next((s.code for s in specs if s.code in text or s.name.lower() in text), None)

    min_grade = None
    for g in GRADE_ORDER:
        if g in text:
            min_grade = Grade(g)
    if min_grade is None and any(w in text for w in ("опыт от", "ведущий", "старший")):
        min_grade = Grade.senior

    KNOWN_STACK = [
        "python", "fastapi", "django", "go", "java", "kotlin", "c++", "c#",
        "react", "vue", "next.js", "typescript", "javascript", "node.js",
        "postgresql", "mysql", "redis", "kafka", "docker", "kubernetes",
        "sql", "ml", "pytorch", "tensorflow", "spark", "airflow",
    ]
    return {"specialization_code": spec_code, "min_grade": min_grade,
            "stack": [t for t in KNOWN_STACK if t in text]}


async def build_shortlist(
    db: AsyncSession, need: EmployerNeed, limit: int = 20, only_fsp: bool = False,
    blind: bool = False,
) -> list[dict]:
    from app.models import Specialization, Microtask, MicrotaskStatus
    spec_names = {s.code: s.name for s in (await db.execute(select(Specialization))).scalars().all()}
    need_vec = text_vector(need.raw_text or " ".join(need.stack or []))
    solved_ids = set((await db.execute(
        select(Microtask.candidate_id).where(
            Microtask.status.in_([MicrotaskStatus.solved, MicrotaskStatus.approach]),
            Microtask.answered_at >= datetime.now(timezone.utc) - timedelta(days=14),
        )
    )).scalars().all())
    candidates = (
        await db.execute(select(CandidateProfile).where(
            CandidateProfile.is_public.is_(True),
            CandidateProfile.grade.is_not(None),
            CandidateProfile.consent_data_processing.is_(True),
        ))
    ).scalars().all()

    need_grade_idx = GRADE_ORDER.index(need.min_grade.value) if need.min_grade else None
    cats = (await db.execute(select(CandidateCategory))).scalars().all()
    cats_by_candidate: dict[str, list] = {}
    for cat in cats:
        cats_by_candidate.setdefault(str(cat.candidate_id), []).append(cat)

    out = []
    for c in candidates:
        my_cats = cats_by_candidate.get(str(c.user_id), [])
        if need.specialization_code:
            cat = next((x for x in my_cats if x.specialization_code == need.specialization_code), None)
            if cat is None:
                continue
        else:
            cat = max(my_cats, key=lambda x: x.theta, default=None)
        if cat is None:
            continue
        if need_grade_idx is not None and GRADE_ORDER.index(cat.grade.value) < need_grade_idx:
            continue
        if only_fsp and not c.fsp_history:
            continue

        score, breakdown = compute_score(c, need.stack or [], theta_override=cat.theta,
                                         solved_recent=str(c.user_id) in solved_ids,
                                         need_vec=need_vec)
        top2 = sorted(breakdown.values(), key=lambda v: v["contribution"], reverse=True)[:2]
        rationale = (
            f"Категория {spec_names.get(cat.specialization_code, cat.specialization_code)} · {GRADE_RU[cat.grade.value]}; "
            + ", ".join(f"{v['label'].lower()}: {v['value']:.0%}" for v in top2)
            + (" · есть подтверждённые достижения ФСП" if c.fsp_history else "")
        )
        out.append({
            "candidate_id": str(c.user_id),
            "full_name": c.full_name,
            "category": category_ru(spec_names.get(cat.specialization_code, cat.specialization_code), cat.grade.value),
            "grade": cat.grade.value,
            "specialization": cat.specialization_code,
            "stack": c.stack,
            "experience_years": c.experience_years,
            "has_fsp": bool(c.fsp_history),
            "integrity": round(c.integrity, 2) if c.integrity is not None else 1.0,
            "integrity_flag": (
                "⚠ по результатам теста были признаки посторонней помощи"
                if (c.integrity or 1.0) < 0.8 else ""
            ),
            "score": round(score, 3),
            "breakdown": breakdown,
            "rationale": rationale,
        })
    out.sort(key=lambda x: x["score"], reverse=True)
    top = out[0] if out else None
    for i, item in enumerate(out):
        if i == 0 or top is None:
            item["gaps"] = []
            continue
        gaps = []
        for key in breakdown_order:
            dv = round(top["breakdown"][key]["contribution"] - item["breakdown"][key]["contribution"], 3)
            if dv > 0.005:
                gaps.append({"label": item["breakdown"][key]["label"],
                             "delta": dv})
        item["gaps"] = gaps
        item["gap_note"] = (
            "проигрывает лидеру: " + ", ".join(
                f"{g['label'].lower()} (−{g['delta']:.2f})" for g in gaps[:3])
        ) if gaps else ""
    top = out[:limit]
    if blind:
        for item in top:
            item["full_name"] = "Кандидат №" + str(item["candidate_id"])[:4].upper()
    return top


def freshness_days_left(last_activity_at: datetime | None, threshold: float = 0.25) -> int:
    """Сколько дней осталось, пока «пульс» профиля не упадёт до порога."""
    if last_activity_at is None:
        return 0
    days = max(0.0, (datetime.now(timezone.utc) - last_activity_at).total_seconds() / 86400)
    now_level = math.exp(-days / 21.0)
    if now_level <= threshold:
        return 0
    return int(round(21.0 * math.log(now_level / threshold)))


KEYBOARD_RU = "йцукенгшщзхъфывапролджэячсмитьбюё"
KEYBOARD_EN = "qwertyuiop[]asdfghjkl;'zxcvbnm,.`"

SYNONYMS = {
    "реакт": "react", "реактом": "react", "рекат": "react", "реактjs": "react",
    "вью": "vue", "вьюjs": "vue", "анжуляр": "angular", "антуляр": "angular",
    "торч": "pytorch", "тенсорфлоу": "tensorflow", "нейросети": "ml", "нейросетей": "ml",
    "нейронки": "ml", "машинное обучение": "ml", "машиное обучение": "ml",
    "постгрес": "postgresql", "постгре": "postgresql", "монго": "mongodb",
    "эластик": "elasticsearch", "кластер кубер": "kubernetes", "кубер": "kubernetes",
    "кубернетис": "kubernetes", "докер": "docker", "кейфка": "kafka", "кафка": "kafka",
    "бэкенд": "backend", "бакенд": "backend", "бекенд": "backend", "фронтенд": "frontend",
    "фронтендер": "frontend", "фулстак": "fullstack", "джуниор": "junior",
    "мидл": "middle", "сеньор": "senior", "лид": "lead", "тимлид": "lead",
    "джанго": "django", "фастапи": "fastapi", "сиквел": "sql", "скл": "sql",
    "объектно-ориентированное": "oop", "джс": "javascript", "тс": "typescript",
    "табличный": "sql", "бд": "sql", "базы данных": "sql", "опенсиви": "opencv",
    "компьютерное зрение": "cv", "компзрени": "cv",
}

_TOKEN_RE = re.compile(r"[a-zа-яё0-9+#.\-]{2,}")


def translate_layout(text: str) -> str:
    """Перекладка раскладки: «въпросы»→ «dfgkbp» нет — только ru→en и en→ru
    для латинских фрагментов, набранных в русской раскладке, и наоборот."""
    out = text
    table_en = str.maketrans(KEYBOARD_RU, KEYBOARD_EN)
    table_ru = str.maketrans(KEYBOARD_EN, KEYBOARD_RU)
    for tok in _TOKEN_RE.findall(text):
        if re.fullmatch(r"[а-яё]+", tok):
            en = tok.translate(table_en)
            if re.fullmatch(r"[a-z]+", en):
                out = out.replace(tok, f"{tok} {en}")
        elif re.fullmatch(r"[a-z]+", tok) and len(tok) > 2:
            ru = tok.translate(table_ru)
            if re.fullmatch(r"[а-яё]+", ru):
                out = out.replace(tok, f"{tok} {ru}")
    return out


def normalize_text(text: str) -> str:
    """Единая нормализация: раскладка → нижний регистр → синонимы → токены."""
    text = translate_layout(text.lower().replace("ё", "е"))
    for k, v in sorted(SYNONYMS.items(), key=lambda kv: -len(kv[0])):
        text = re.sub(rf"(?<!\w){re.escape(k)}(?!\w)", v, text)
    return " ".join(_TOKEN_RE.findall(text))


def text_vector(text: str, dim: int = 256):
    """Хэш-вектор bag-of-words (256): без тяжёлой модели, ловит пересечение
    слов и фраз; нормализован под косинусную близость (pgvector <=>)."""
    import hashlib
    vec = [0.0] * dim
    toks = normalize_text(text).split()
    for tok in toks:
        idx = int(hashlib.md5(tok.encode()).hexdigest(), 16) % dim
        vec[idx] += 1.0
    n = sum(v * v for v in vec) ** 0.5
    return [v / n for v in vec] if n else vec


def cosine(a: list, b: list) -> float:
    return sum(x * y for x, y in zip(a, b))


def match_semantic(candidate_doc: str, need_vec: list) -> float:
    """Косинусная близость документа кандидата к вектору потребности."""
    cvec = text_vector(candidate_doc)
    return max(0.0, min(1.0, cosine(cvec, need_vec)))
