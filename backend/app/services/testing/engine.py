import random
from datetime import datetime, timedelta, timezone

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import (
    GRADE_ORDER,
    CandidateCategory,
    CandidateProfile,
    EmployerCustomItem,
    Grade,
    ItemTemplate,
    TestAnswer,
    TestBlueprint,
    TestSession,
    TestStatus,
)
from app.services.scoring import theta_to_grade, final_score, board_key
from app.core.redisio import client as redis_client
from app.services.testing.blueprint import blueprint_pool

GRID = np.linspace(-4.0, 4.0, 161)
PRIOR_VAR = 2.0
MAX_EXPOSURE = 50
GRADE_TARGET_BY_CURRENT = {
    Grade.junior: -1.5,
    Grade.middle: -0.5,
    Grade.senior: 0.5,
    Grade.lead: 1.5,
}


def irt_prob(theta, a, b, c=0.0):
    return c + (1 - c) / (1 + np.exp(-a * (theta - b)))


def irt_info(theta, a, b, c=0.0):
    p = np.clip(irt_prob(theta, a, b, c), 1e-9, 1 - 1e-9)
    q = 1 - p
    return a**2 * (q / p) * ((p - c) / (1 - c)) ** 2


def estimate_theta_eap(history: list[tuple]) -> float:
    loglik = np.zeros_like(GRID)
    for a, b, c, correct in history:
        p = np.clip(irt_prob(GRID, a, b, c), 1e-9, 1 - 1e-9)
        loglik += np.log(p) if correct else np.log(1 - p)
    loglik -= GRID**2 / (2 * PRIOR_VAR)
    post = np.exp(loglik - loglik.max())
    post /= post.sum()
    return float(np.sum(GRID * post))


def standard_error(history: list[tuple], theta: float) -> float:
    if not history:
        return 1.5
    info = sum(irt_info(theta, a, b, c) for a, b, c, _ in history)
    return float(1.0 / np.sqrt(info)) if info > 0 else 1.5


CODE_LANGUAGES = ["python", "javascript", "c++", "c#", "java"]


def _loop_code(lang: str, depth: int) -> str:
    if lang == "python":
        body = ""
        for d in range(depth):
            body += "    " * (d + 1) + f"for i{d} in range(n):\n"
        body += "    " * (depth + 1) + "counter += 1"
        return f"```python\ndef f(n):\n    counter = 0\n{body}\n    return counter\n```"
    if lang == "javascript":
        body = ""
        for d in range(depth):
            body += "  " * (d + 1) + f"for (let i{d} = 0; i{d} < n; i{d}++) {{\n"
        body += "  " * (depth + 1) + "counter++;\n" + "  " * depth + "}"
        return f"```javascript\nfunction f(n) {{\n  let counter = 0;\n{body}\n  return counter;\n}}\n```"
    inc = "++"
    body = ""
    for d in range(depth):
        body += "    " * (d + 1) + f"for (int i{d} = 0; i{d} < n; i{d}{inc}) {{\n"
    body += "    " * (depth + 1) + "counter++;\n" + "    " * depth + "}"
    lang_name = {"c++": "cpp", "c#": "csharp", "java": "java"}[lang]
    return f"```{lang_name}\nint counter = 0;\n{body}\n```"


def gen_loop_complexity(rng: random.Random, params: dict) -> dict:
    depth = rng.randint(params.get("min_depth", 2), params.get("max_depth", 3))
    lang = params.get("language", "python")
    code = _loop_code(lang, depth)
    body = code + "\nАсимптотика?"
    correct = f"O(n^{depth})"
    options = [f"O(n^{depth})", "O(n)", f"O(2^{depth})", "O(log n)"]
    if depth == 1:
        options[1] = "O(n·log n)"
    rng.shuffle(options)
    return {"body": body, "options": options, "answer": options.index(correct), "answer_type": "choice"}


def gen_code_output(rng: random.Random, params: dict) -> dict:
    mode = rng.choice(params.get("modes", ["recursion", "arithmetic"]))
    lang = params.get("language", "python")
    if mode == "recursion":
        n = rng.randint(6, 10)
        a, b = rng.randint(2, 4), rng.randint(2, 5)
        if lang == "python":
            code = (f"def g(n):\n    if n <= 1:\n        return {a}\n"
                    f"    return g(n - 1) + {b}\n\nprint(g({n}))")
            code = f"```python\n{code}\n```"
        elif lang == "javascript":
            code = (f"function g(n) {{ if (n <= 1) return {a}; return g(n - 1) + {b}; }}\n"
                    f"console.log(g({n}))")
            code = f"```javascript\n{code}\n```"
        elif lang == "c++":
            code = (f"int g(int n) {{ return n <= 1 ? {a} : g(n - 1) + {b}; }}\n"
                    f"cout << g({n});")
            code = f"```cpp\n{code}\n```"
        elif lang == "c#":
            code = (f"static int G(int n) {{ return n <= 1 ? {a} : G(n - 1) + {b}; }}\n"
                    f"Console.WriteLine(G({n}));")
            code = f"```csharp\n{code}\n```"
        else:
            code = (f"static int g(int n) {{ if (n <= 1) return {a}; return g(n - 1) + {b}; }}\n"
                    f"System.out.println(g({n}));")
            code = f"```java\n{code}\n```"
        body = "Что выведет код?\n\n" + code
        correct = str(a + b * (n - 1))
    else:
        x, y, z = (rng.randint(2, 9) for _ in range(3))
        total = x + y + z + x + y + z * 2 - y
        if lang == "python":
            code = (f"xs = [{x}, {y}, {z}, {x + y}]\nxs.append(z * 2)\nprint(sum(xs) - {y})")
            code = f"```python\n{code}\n```"
        elif lang == "javascript":
            code = (f"const xs = [{x}, {y}, {z}, {x + y}];\nxs.push(z * 2);\n"
                    f"console.log(xs.reduce((s, v) => s + v, 0) - {y})")
            code = f"```javascript\n{code}\n```"
        elif lang == "c++":
            code = (f"vector<int> xs = {{{x}, {y}, {z}, {x + y}}};\nxs.push_back(z * 2);\n"
                    f"int s = 0; for (int v : xs) s += v;\ncout << s - {y};")
            code = f"```cpp\n{code}\n```"
        elif lang == "c#":
            code = (f"var xs = new[] {{{x}, {y}, {z}, {x + y}}};\nvar ys = xs.Append(z * 2);\n"
                    f"Console.WriteLine(ys.Sum() - {y});")
            code = f"```csharp\n{code}\n```"
        else:
            code = (f"int[] xs = {{{x}, {y}, {z}, {x + y}}};\nint s = Arrays.stream(xs).sum() + z * 2;\n"
                    f"System.out.println(s - {y});")
            code = f"```java\n{code}\n```"
        body = "Что выведет код?\n\n" + code
        correct = str(total)
    options = [correct]
    while len(options) < 4:
        wrong = str(int(correct) + rng.choice([-3, -2, -1, 1, 2, 3]) * rng.randint(1, 4))
        if wrong not in options:
            options.append(wrong)
    rng.shuffle(options)
    return {"body": body, "options": options, "answer": options.index(correct), "answer_type": "choice"}


def gen_sql_select(rng: random.Random, params: dict) -> dict:
    table = rng.choice(["orders", "employees", "products"])
    col = rng.choice(["price", "salary", "amount"])
    body = f"Таблица {table}: id, {col}, created_at.\nКакой запрос вернёт среднее значение {col} по месяцам?"
    correct = f"SELECT date_trunc('month', created_at) AS m, AVG({col}) FROM {table} GROUP BY m ORDER BY m"
    options = [
        correct,
        f"SELECT created_at, AVG({col}) FROM {table} ORDER BY created_at",
        f"SELECT date_trunc('month', created_at), SUM({col}) FROM {table} ORDER BY created_at",
    ]
    rng.shuffle(options)
    return {"body": body, "options": options, "answer": options.index(correct), "answer_type": "choice"}


def gen_string_algo(rng: random.Random, params: dict) -> dict:
    s = "".join(rng.choice("abcde") for _ in range(rng.randint(5, 8)))
    lang = params.get("language", "python")
    if lang == "python":
        fence, code = "python", (
            f"s = '{s}'\nprint(len(set(s)) * (s.count(s[0]) - 1))")
    elif lang == "javascript":
        fence, code = "javascript", (
            f"const s = '{s}';\nconst u = new Set(s).size;\n"
            f"console.log(u * (s.split('').filter(c => c === s[0]).length - 1));")
    elif lang == "c++":
        fence, code = "cpp", (
            f'string s = "{s}";\nset<char> u(s.begin(), s.end());\n'
            f"cout << u.size() * (count(s.begin(), s.end(), s[0]) - 1);")
    elif lang == "c#":
        fence, code = "csharp", (
            f'string s = "{s}";\nint u = s.Distinct().Count();\n'
            f"Console.WriteLine(u * (s.Count(c => c == s[0]) - 1));")
    else:
        fence, code = "java", (
            f'String s = "{s}";\nint u = (int) s.chars().distinct().count();\n'
            f"int rep = 0; for (char c : s.toCharArray()) if (c == s.charAt(0)) rep++;\n"
            f"System.out.println(u * (rep - 1));")
    body = "Что выведет код?\n\n```" + fence + "\n" + code + "\n```"
    correct = str(len(set(s)) * (s.count(s[0]) - 1))
    base = int(correct)
    wrongs = rng.sample([n for n in range(0, max(4, base + 4)) if n != base], 3)
    options = [correct, *[str(w) for w in wrongs]]
    rng.shuffle(options)
    return {"body": body, "options": options, "answer": options.index(correct), "answer_type": "choice"}


def _quiz_from_bank(rng: random.Random, questions: list, params: dict) -> dict:
    q, correct, wrongs = rng.choice(questions)
    options = [correct, *wrongs]
    rng.shuffle(options)
    return {"body": q, "options": options, "answer": options.index(correct), "answer_type": "choice"}


def gen_ml_theory(rng: random.Random, params: dict) -> dict:
    return _quiz_from_bank(rng, params.get("questions", [
        ("Модель показывает 99% на train и 60% на test. Это…", "переобучение (overfitting)",
         ["недообучение", "нормальная генерализация", "утечка данных в трейне"]),
        ("Выберите метрику для классификации при дисбалансе 1:1000.", "F1 / precision-recall",
         ["accuracy", "MSE", "R²"]),
        ("Кросс-валидация нужна, чтобы…", "оценить генерализацию устойчивее, чем один сплит",
         ["ускорить обучение", "уменьшить размер датасета", "повысить accuracy на train"]),
        ("L1-регуляризация отличается от L2 тем, что…", "обнуляет часть весов (отбор признаков)",
         ["всегда лучше по качеству", "не влияет на веса", "работает только с деревьями"]),
        ("Градиентный спуск находит…", "локальный минимум функции потерь",
         ["глобальный минимум всегда", "нуль градиента функции данных", "максимум правдоподобия"]),
    ]), params)


def gen_hr_labor_code(rng: random.Random, params: dict) -> dict:
    return _quiz_from_bank(rng, params.get("questions", [
        ("Максимальный испытательный срок для рядового сотрудника (без руководящих позиций)?",
         "3 месяца", ["6 месяцев", "12 месяцев", "испытательный срок не ограничен"]),
        ("Продолжительность основного ежегодного оплачиваемого отпуска?",
         "28 календарных дней", ["14 календарных дней", "20 рабочих дней", "30 календарных дней"]),
        ("За сколько дней работодатель обязан предупредить об увольнении при сокращении?",
         "не менее чем за 2 месяца", ["за 2 недели", "за 1 месяц", "за 3 месяца"]),
        ("В каком сроке должен быть заключён трудовой договор после фактического допуска к работе?",
         "в течение 3 рабочих дней", ["в тот же день", "в течение 10 дней", "в течение месяца"]),
        ("Максимальный срок, на который может заключаться срочный трудовой договор (общий случай)?",
         "5 лет", ["1 год", "3 года", "не ограничен"]),
    ]), params)


def gen_office_records(rng: random.Random, params: dict) -> dict:
    return _quiz_from_bank(rng, params.get("questions", [
        ("Реквизит «дата документа» оформляется…", "датой подписания (или утверждения) документа",
         ["датой поступления в организацию", "датой составления проекта всегда", "любой датой на выбор"]),
        ("Номенклатура дел — это…", "систематизированный перечень дел организации с сроками хранения",
         ["график отпусков сотрудников", "реестр входящих писем", "штатное расписание"]),
        ("Срок хранения большинства управленческих документов (приказы по основной деятельности)?",
         "постоянно", ["1 год", "5 лет", "10 лет"]),
        ("Регистрация входящих документов означает…", "запись данных документа в учётную форму с присвоением номера",
         ["передачу руководителю", "сканирование документа", "ответ отправителю"]),
        ("Контроль исполнения документа — это…", "отслеживание хода исполнения и снятие с контроля по завершении",
         ["проверка орфографии", "архивирование копии", "пересылка в смежный отдел"]),
    ]), params)


def gen_qa_design(rng: random.Random, params: dict) -> dict:
    return _quiz_from_bank(rng, params.get("questions", [
        ("Поле принимает возраст 18–60. Сколько проверок минимально покрывают классы эквивалентности и границы?",
         "5–6 значений (границы ±1 и внутри класса)", ["1 значение (30)", "60 значений — все", "все числа от 0 до 100"]),
        ("Смок-тест — это…", "быстрая проверка ключевой функциональности до углублённого тестирования",
         ["тест на нагрузку", "проверка интерфейса пиксель-в-пиксель", "тест безопасности"]),
        ("Баг переоткрыт — что это значит?", "после исправления дефект воспроизвёлсь снова",
         ["баг вне скоупа", "дубль другого бага", "баг фичи, которой нет в ТЗ"]),
        ("Приоритет и серьёзность бага — это…", "разные атрибуты: важность исправления и степень ущерба",
         ["синонимы", "приоритет задаёт разработчик, серьёзность — нет", "одно и то же с разной шкалой"]),
    ]), params)


def gen_frontend_react(rng: random.Random, params: dict) -> dict:
    return _quiz_from_bank(rng, params.get("questions", [
        ("Что делает хук useEffect с пустым массивом зависимостей?",
         "выполняется один раз после первого рендера", ["перед каждым рендером", "каждый раз при любом состоянии", "никогда"]),
        ("Props в React — это…", "входные данные компонента, доступные только для чтения",
         ["локальное изменяемое состояние", "глобальный кеш", "CSS-классы компонента"]),
        ("let x = 5; x = x + '5'; чему равен x?", "'55' (строка)", ["10 (число)", "NaN", "ошибка типов"]),
        ("Что вернёт typeof null?", "'object'", ["'null'", "'undefined'", "'number'"]),
        ("Ключи (key) в списках React нужны для…", "эффективного обновления элементов при ререндере",
         ["сортировки списка", "валидации типов", "стилизации"]),
    ]), params)


def gen_ml_metric_calc(rng: random.Random, params: dict) -> dict:
    tp, fp, fn = rng.randint(20, 80), rng.randint(5, 40), rng.randint(5, 40)
    metric = rng.choice(["precision", "recall"])
    if metric == "precision":
        correct = f"{tp / (tp + fp):.2f}"
        body = f"TP={tp}, FP={fp}, FN={fn}. Чему равна precision?\n(ответ в формате 0.XX)"
    else:
        correct = f"{tp / (tp + fn):.2f}"
        body = f"TP={tp}, FP={fp}, FN={fn}. Чему равен recall?\n(ответ в формате 0.XX)"
    return {"body": body, "answer": correct, "answer_type": "exact"}


def gen_analytics_metric(rng: random.Random, params: dict) -> dict:
    kind = rng.choice(["conversion", "retention", "arpu"])
    if kind == "conversion":
        visitors, buyers = rng.randint(5000, 20000), rng.randint(50, 800)
        return {"body": f"На сайт зашло {visitors} посетителей, купили {buyers}. Конверсия (0.XXX)?",
                "answer": f"{buyers / visitors:.3f}", "answer_type": "exact"}
    if kind == "retention":
        installed = rng.randint(1000, 5000)
        returned = rng.randint(100, installed // 2)
        return {"body": f"Установили приложение {installed} пользователей, на 7-й день вернулись {returned}. Retention day 7 (0.XX)?",
                "answer": f"{returned / installed:.2f}", "answer_type": "exact"}
    revenue, users = rng.randint(100000, 500000), rng.randint(2000, 20000)
    return {"body": f"Выручка {revenue} руб., активных пользователей {users}. ARPU (руб., 1 знак)?",
            "answer": str(round(revenue / users, 1)), "answer_type": "exact"}


GENERATORS = {
    "loop_complexity": gen_loop_complexity,
    "code_output": gen_code_output,
    "sql_select": gen_sql_select,
    "string_algo": gen_string_algo,
    "ml_theory": gen_ml_theory,
    "ml_metric_calc": gen_ml_metric_calc,
    "hr_labor_code": gen_hr_labor_code,
    "office_records": gen_office_records,
    "qa_design": gen_qa_design,
    "analytics_metric": gen_analytics_metric,
    "frontend_react": gen_frontend_react,
}


def sessions_history(sessions) -> list[dict]:
    """История попыток по направлениям: балл, грейд, честность; лучший балл."""
    groups: dict[str, list] = {}
    for s in sessions:
        groups.setdefault(s.specialization_code, []).append({
            "date": s.finished_at.isoformat()[:10] if s.finished_at else None,
            "score": final_score(s.theta, s.integrity),
            "grade": s.measured_grade.value if s.measured_grade else None,
            "integrity": round(s.integrity, 2),
        })
    return [
        {"specialization": spec, "attempts": attempts,
         "best_score": max(a["score"] for a in attempts)}
        for spec, attempts in groups.items()
    ]


async def start_session(
    db: AsyncSession, candidate: CandidateProfile, specialization_code: str,
    target_grade: Grade, is_initial: bool, blueprint_id: str | None = None,
    code_language: str = "python",
) -> TestSession:
    for stale in (await db.execute(
        select(TestSession).where(
            TestSession.candidate_id == candidate.user_id,
            TestSession.status == TestStatus.in_progress,
        )
    )).scalars().all():
        stale.status = TestStatus.abandoned
    session = TestSession(
        candidate_id=candidate.user_id,
        specialization_code=specialization_code,
        target_grade=target_grade,
        is_initial=is_initial,
        blueprint_id=blueprint_id,
        code_language=code_language,
        theta=GRADE_TARGET_BY_CURRENT[target_grade],
    )
    db.add(session)
    await db.flush()
    return session


async def next_item(db: AsyncSession, session: TestSession) -> dict | None:
    if session.blueprint_id:
        bp = await db.get(TestBlueprint, session.blueprint_id)
        pool = blueprint_pool(bp) if bp is not None and bp.status == "published" else []
    else:
        rows = (await db.execute(
            select(ItemTemplate).where(
                ItemTemplate.specialization_code == session.specialization_code,
                ItemTemplate.is_active.is_(True),
                ItemTemplate.exposure_count < MAX_EXPOSURE,
            )
        )).scalars().all()
        pool = [
            {"id": str(it.id), "kind": it.kind.value, "a": it.a, "b": it.b, "c": it.c,
             "title": it.title, "template_params": it.template_params}
            for it in rows
        ]

    answered = {e["item_id"] for e in session.administered}
    pool = [it for it in pool if it["id"] not in answered]

    item, best_info = None, -1.0
    for it in pool:
        info = float(irt_info(session.theta, it["a"], it["b"], it["c"]))
        if info > best_info:
            item, best_info = it, info
    if item is None:
        return None

    if item.get("is_custom"):
        custom = item["template_params"]["custom"]
        options = list(custom.get("options", []))
        correct_text = custom["correct"]
        if options and correct_text not in options:
            options.append(correct_text)
        random.shuffle(options)
        variant = (
            {"body": custom["body"], "options": options,
             "answer": options.index(correct_text), "answer_type": "choice"}
            if options else
            {"body": custom["body"], "answer": correct_text, "answer_type": "exact"}
        )
    else:
        gen = GENERATORS[item["template_params"]["generator"]]
        params = dict(item["template_params"].get("params", {}))
        params["language"] = params.get("language") or session.code_language
        variant = gen(random.Random(), params)

    session.administered = session.administered + [{
        "item_id": item["id"],
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "variant": {
            "body": variant["body"], "options": variant.get("options"),
            "answer": variant.get("answer"), "answer_type": variant.get("answer_type"),
            "kind": item["kind"],
        },
    }]
    it_db = await db.get(ItemTemplate, item["id"])
    if it_db:
        it_db.exposure_count += 1
        if it_db.exposure_count >= MAX_EXPOSURE:
            it_db.is_active = False
    await db.flush()

    return {
        "item_id": item["id"],
        "title": item["title"],
        "body": variant["body"],
        "options": variant.get("options"),
        "number": len(session.administered),
    }


MIN_ANSWER_MS = {"quiz": 3500, "exact": 12000}
AWAY_SIGNAL_MS = 8000


async def submit_answer(
    db: AsyncSession, session: TestSession, item_id: str, payload: dict,
    time_spent_ms: int = 0, away_ms: int = 0, tab_switches: int = 0,
) -> dict:
    if session.status != TestStatus.in_progress:
        raise ValueError("Тест уже завершён")

    entry = next((e for e in session.administered if e["item_id"] == item_id), None)
    if entry is None:
        raise ValueError("Это задание не выдавалось в текущей сессии")
    answered = (await db.execute(
        select(TestAnswer.id).where(
            TestAnswer.session_id == session.id, TestAnswer.item_id == item_id)
    )).scalar()
    if answered is not None:
        raise ValueError("Ответ по этому заданию уже принят")
    variant = entry["variant"]

    correct = (
        payload.get("choice") == variant.get("answer")
        if variant.get("answer_type") == "choice"
        else str(payload.get("value", "")).strip() == str(variant.get("answer", "")).strip()
    )

    kind = "quiz" if variant.get("answer_type") == "choice" else "exact"
    elapsed_ms = 0
    if entry.get("issued_at"):
        issued = datetime.fromisoformat(entry["issued_at"])
        elapsed_ms = max(0, int((datetime.now(timezone.utc) - issued).total_seconds() * 1000))
    signals = 0
    if correct and elapsed_ms and elapsed_ms < MIN_ANSWER_MS.get(kind, 3500):
        signals += 1
    if correct and away_ms > AWAY_SIGNAL_MS:
        signals += 1
    session.integrity = max(0.0, session.integrity - 0.15 * signals)
    session.away_total_ms += max(0, away_ms)
    session.tab_switches += max(0, tab_switches)

    db.add(TestAnswer(
        session_id=session.id, item_id=item_id, answer=payload,
        correct=correct,
        variant={"body": variant["body"], "options": variant.get("options")},
        time_spent_ms=max(0, time_spent_ms), away_ms=max(0, away_ms),
        tab_switches=max(0, tab_switches), cheat_signals=signals,
    ))

    rows = (await db.execute(
        select(TestAnswer.item_id, TestAnswer.correct)
        .where(TestAnswer.session_id == session.id)
        .order_by(TestAnswer.created_at)
    )).all()
    ids = [i for i, _ in rows]
    params_bank = {
        str(r.id): (r.a, r.b, r.c) for r in (
            await db.execute(select(ItemTemplate).where(ItemTemplate.id.in_(ids)))
        ).scalars().all()
    }
    params_custom = {
        str(r.id): (r.a, r.b, r.c) for r in (
            await db.execute(select(EmployerCustomItem).where(EmployerCustomItem.id.in_(ids)))
        ).scalars().all()
    }
    history = [
        (*(params_bank.get(i) or params_custom.get(i) or (1.5, 0.0, 0.25)), ok)
        for i, ok in rows
    ]

    session.theta = estimate_theta_eap(history)
    session.se = standard_error(history, session.theta)
    result = {"correct": correct, "theta": round(session.theta, 3), "se": round(session.se, 3)}

    finished = session.se <= settings.cat_se_threshold or len(session.administered) >= settings.cat_target_items
    if finished:
        result.update(await finish_session(db, session))
    else:
        nxt = await next_item(db, session)
        if nxt is None:
            result.update(await finish_session(db, session))
            result["note"] = "тест завершён: задания пула исчерпаны"
        else:
            result["next_item"] = nxt
    return result


async def finish_session(db: AsyncSession, session: TestSession) -> dict:
    candidate = await db.get(CandidateProfile, session.candidate_id)

    session.status = TestStatus.completed
    session.finished_at = datetime.now(timezone.utc)
    session.measured_grade = Grade(theta_to_grade(session.theta))

    applied = session.measured_grade
    cooldown_note = None
    if not session.is_initial and candidate.grade is not None:
        rising = GRADE_ORDER.index(applied.value) > GRADE_ORDER.index(candidate.grade.value)
        in_cooldown = (
            candidate.last_grade_change_at is not None
            and datetime.now(timezone.utc) - candidate.last_grade_change_at
            < timedelta(days=settings.grade_change_cooldown_days)
        )
        if rising and applied != candidate.grade and in_cooldown:
            applied = candidate.grade
            cooldown_note = (
                f"Повышение грейда доступно не чаще раза в "
                f"{settings.grade_change_cooldown_days} дней. Зафиксирован грейд "
                f"{candidate.grade.value}."
            )

    cat = (await db.execute(
        select(CandidateCategory).where(
            CandidateCategory.candidate_id == candidate.user_id,
            CandidateCategory.specialization_code == session.specialization_code,
        )
    )).scalar_one_or_none()
    best_note = None
    prev_grade = candidate.grade
    session.applied_grade = applied
    best = cat is None or session.theta > cat.theta

    if cat is None:
        db.add(CandidateCategory(
            candidate_id=candidate.user_id,
            specialization_code=session.specialization_code,
            grade=applied, theta=session.theta, theta_se=session.se,
        ))
    elif best:
        cat.grade = applied
        cat.theta = session.theta
        cat.theta_se = session.se
        cat.updated_at = datetime.now(timezone.utc)
    else:
        best_note = (
            f"Лучший результат этой категории сохранён: θ = {round(cat.theta, 2)} "
            f"({cat.grade.value}); новая попытка слабее"
        )

    profile_best = candidate.grade is None or session.theta >= (
        candidate.theta if candidate.theta is not None else -99.0)
    if profile_best:
        candidate.grade = applied
        candidate.specialization_code = session.specialization_code
        candidate.theta = session.theta
        candidate.theta_se = session.se
        candidate.integrity = session.integrity
        if prev_grade != applied:
            candidate.last_grade_change_at = datetime.now(timezone.utc)
    candidate.theta_history = (candidate.theta_history or []) + [round(session.theta, 3)]
    candidate.last_activity_at = datetime.now(timezone.utc)

    try:
        await redis_client.zadd(
            f"leaderboard:{session.specialization_code}",
            {str(candidate.user_id): board_key(session.theta, session.integrity)}, gt=True)
    except Exception:
        pass

    return {
        "finished": True,
        "measured_grade": session.measured_grade.value,
        "applied_grade": applied.value,
        "category": f"{candidate.specialization_code} · {applied.value}",
        "cooldown_note": cooldown_note,
        "theta": round(session.theta, 3),
        "se": round(session.se, 3),
        "integrity": round(session.integrity, 2),
        "integrity_note": (
            "Замечено переключение вкладок / слишком быстрые ответы — это снижает доверие к результату"
            if session.integrity < 1.0 else None
        ),
        "best_note": best_note,
        "score": final_score(session.theta, session.integrity),
    }
