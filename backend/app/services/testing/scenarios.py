
from dataclasses import dataclass, field
from app.services.scoring import GRADE_RU, theta_to_grade



@dataclass
class Scenario:
    spec_code: str
    spec_name: str
    spec_description: str
    survey_options: list[str]
    stack_tags: list[str] = field(default_factory=list)
    generators: dict[str, int] = field(default_factory=dict)
    difficulty_span: tuple[float, float] = (-2.0, 2.0)
    demo_vacancies: list[dict] = field(default_factory=list)

SCENARIOS: list[Scenario] = [
    Scenario(
        spec_code="backend",
        stack_tags=['python', 'fastapi', 'postgresql', 'docker', 'redis', 'kafka', 'go'],
        spec_name="Бэкенд-разработчик",
        spec_description="Серверная разработка: API, базы данных, интеграции",
        survey_options=["Веб-разработка", "Enterprise-системы", "Микросервисы", "Телеком", "Финтех"],
        generators={"loop_complexity": 3, "code_output": 4, "sql_select": 3, "string_algo": 2},
        demo_vacancies=[
            {"title": "Бэкенд-разработчик Python", "stack": ["python", "fastapi", "postgresql", "docker"],
             "min_grade": "middle", "salary_min": 180000, "salary_max": 300000,
             "description": "Разработка API высоконагруженной платформы: FastAPI, PostgreSQL, интеграции с внешними системами."},
            {"title": "Backend Go-разработчик", "stack": ["go", "postgresql", "kafka", "kubernetes"],
             "min_grade": "senior", "salary_min": 280000, "salary_max": 450000,
             "description": "Высоконагруженные сервисы платёжного шлюза: Go, Kafka, Kubernetes."},
            {"title": "Python-разработчик (интеграции)", "stack": ["python", "django", "postgresql", "redis"], "min_grade": "junior", "salary_min": 90000, "salary_max": 160000, "description": "Внутренние сервисы ритейл-сети: каталог, остатки, интеграции с кассами."},
            {"title": "Геймдев-бэкенд (Go)", "stack": ["golang", "redis", "kafka"], "min_grade": "senior", "salary_min": 320000, "salary_max": 500000, "description": "Реалтайм-инфраструктура онлайн-игры: матчмейкинг, лидерборды, телеметрия."},
        ],
    ),
    Scenario(
        spec_code="frontend",
        stack_tags=['react', 'typescript', 'next.js', 'css', 'javascript', 'vue'],
        spec_name="Фронтенд-разработчик",
        spec_description="Клиентская разработка: интерфейсы, SPA, UX",
        survey_options=["Веб-разработка", "E-commerce", "Медиа", "Корпоративные порталы"],
        generators={"frontend_react": 5, "code_output": 3, "string_algo": 2},
        demo_vacancies=[
            {"title": "Frontend-разработчик (React)", "stack": ["react", "typescript", "next.js"],
             "min_grade": "middle", "salary_min": 160000, "salary_max": 280000,
             "description": "Интерфейс B2B-платформы аналитики: React, TypeScript, Next.js."},
            {"title": "Frontend-разработчик (Vue)", "stack": ["vue", "javascript", "css"], "min_grade": "junior", "salary_min": 80000, "salary_max": 140000, "description": "Личный кабинет клиента страховой компании: Vue, адаптивная вёрстка."},
        ],
    ),
    Scenario(
        spec_code="ml",
        stack_tags=['python', 'pytorch', 'ml', 'sql', 'tensorflow', 'spark'],
        spec_name="ML-инженер",
        spec_description="Машинное обучение: модели, пайплайны, внедрение",
        survey_options=["Продуктовый ML", "Computer Vision", "NLP", "Рекомендательные системы", "MLOps"],
        generators={"ml_theory": 5, "ml_metric_calc": 3, "code_output": 2, "sql_select": 2},
        demo_vacancies=[
            {"title": "ML-инженер (NLP)", "stack": ["python", "pytorch", "ml"],
             "min_grade": "senior", "salary_min": 300000, "salary_max": 500000,
             "description": "Развитие семантического поиска: PyTorch, LLM-пайплайны, MLOps."},
            {"title": "Data Scientist (CV)", "stack": ["python", "pytorch", "cv"], "min_grade": "middle", "salary_min": 200000, "salary_max": 350000, "description": "Модели компьютерного зрения для контроля качества на производстве."},
        ],
    ),
    Scenario(
        spec_code="analytics",
        stack_tags=['sql', 'python', 'airflow', 'pandas', 'tableau'],
        spec_name="Аналитик данных",
        spec_description="Аналитика: SQL, метрики, отчётность, A/B",
        survey_options=["Продуктовая аналитика", "BI", "Финансовая аналитика", "Маркетинговая аналитика"],
        generators={"analytics_metric": 4, "sql_select": 4, "code_output": 2},
        demo_vacancies=[
            {"title": "Аналитик данных", "stack": ["sql", "python", "airflow"],
             "min_grade": "middle", "salary_min": 150000, "salary_max": 250000,
             "description": "Продуктовая аналитика маркетплейса: SQL, A/B-эксперименты, дашборды."},
            {"title": "BI-аналитик", "stack": ["sql", "tableau", "power bi"], "min_grade": "junior", "salary_min": 80000, "salary_max": 130000, "description": "Дашборды и отчётность для розницы: продажи, план/факт, воронки."},
        ],
    ),
    Scenario(
        spec_code="qa",
        stack_tags=['python', 'pytest', 'postman', 'sql', 'docker'],
        spec_name="QA-инженер",
        spec_description="Тестирование: тест-дизайн, автотесты, процессы",
        survey_options=["Ручное тестирование", "Автоматизация QA", "Нагрузочное тестирование", "Mobile QA"],
        generators={"qa_design": 5, "code_output": 3, "string_algo": 2},
        demo_vacancies=[
            {"title": "QA-инженер (автотесты)", "stack": ["python", "sql", "docker"],
             "min_grade": "junior", "salary_min": 90000, "salary_max": 180000,
             "description": "Автоматизация регресса веб-приложения: Python, pytest, CI."},
            {"title": "Ручной тестировщик", "stack": ["тест-дизайн", "баг-репорт", "postman"], "min_grade": "junior", "salary_min": 60000, "salary_max": 110000, "description": "Функциональное тестирование мобильного банка по чек-листам."},
        ],
    ),
    Scenario(
        spec_code="hr",
        stack_tags=[],
        spec_name="Кадровик (HR-специалист)",
        spec_description="Кадровая работа: приём/увольнение, кадровые документы, трудовое право",
        survey_options=["Кадровое делопроизводство", "Рекрутмент", "C&B (компенсации)", "HR Generalist"],
        generators={"hr_labor_code": 5, "office_records": 3},
        difficulty_span=(-1.5, 1.5),
        demo_vacancies=[
            {"title": "Специалист по кадровому делопроизводству", "stack": [],
             "min_grade": "middle", "salary_min": 70000, "salary_max": 130000,
             "description": "Полный цикл КДП: приём, переводы, увольнения, отчётность, 1С:ЗУП."},
            {"title": "HR-дженералист", "stack": ["рекрутмент", "онбординг", "тк рф"], "min_grade": "middle", "salary_min": 90000, "salary_max": 150000, "description": "Полный HR-цикл ИТ-компании: найм, адаптация, КДП, корпкультура."},
        ],
    ),
    Scenario(
        spec_code="office_admin",
        stack_tags=[],
        spec_name="Делопроизводитель",
        spec_description="Документооборот: регистрация, номенклатура, архив, контроль исполнения",
        survey_options=["Общий документооборот", "Архивное дело", "Секретариат", "Документооборот в госсекторе"],
        generators={"office_records": 5, "hr_labor_code": 2},
        difficulty_span=(-1.5, 1.5),
        demo_vacancies=[
            {"title": "Делопроизводитель", "stack": [],
             "min_grade": "junior", "salary_min": 50000, "salary_max": 90000,
             "description": "Регистрация входящей/исходящей корреспонденции, архив, СЭД."},
            {"title": "Секретарь-делопроизводитель", "stack": ["делопроизводство", "сэд"], "min_grade": "junior", "salary_min": 45000, "salary_max": 75000, "description": "Документооборот в компании: СЭД, командировки, архив."},
        ],
    ),
    Scenario(
        spec_code="devops",
        stack_tags=['kubernetes', 'docker', 'terraform', 'nginx', 'prometheus'],
        spec_name="DevOps-инженер",
        spec_description="Инфраструктура: CI/CD, контейнеры, мониторинг",
        survey_options=["Облачная инфраструктура", "On-premise", "SRE", "Инфраструктура данных"],
        generators={"loop_complexity": 2, "code_output": 3, "sql_select": 2, "ml_theory": 1},
        demo_vacancies=[
            {"title": "DevOps-инженер", "stack": ["kubernetes", "docker", "kafka"],
             "min_grade": "middle", "salary_min": 220000, "salary_max": 380000,
             "description": "Развитие платформенной инфраструктуры: Kubernetes, GitLab CI, мониторинг."},
            {"title": "SRE-инженер", "stack": ["kubernetes", "prometheus", "linux"], "min_grade": "lead", "salary_min": 380000, "salary_max": 600000, "description": "Надёжность платформы Delivery: SLO, инциденты, автоматизация."},
        ],
    ),
]



def difficulty_grid(n: int, span: tuple[float, float]) -> list[float]:
    import random as _random
    lo, hi = span
    if n == 1:
        return [(lo + hi) / 2]
    step = (hi - lo) / (n - 1)
    return [round(lo + i * step + _random.uniform(-0.15, 0.15), 2) for i in range(n)]

def build_bank_items(scenario: Scenario) -> list[dict]:
    templates = []
    total = sum(scenario.generators.values())
    bs = difficulty_grid(total, scenario.difficulty_span)
    i = 0
    for gen_name, count in scenario.generators.items():
        for k in range(count):
            b = bs[i]

            a = round(1.2 + 1.3 * (1 - abs(b) / 2.5), 2)
            c = 0.25 if gen_name in ("ml_theory", "hr_labor_code", "office_records",
                                     "qa_design", "frontend_react") else 0.05
            templates.append({
                "specialization_code": scenario.spec_code,
                "kind": "quiz",
                "title": f"{GEN_TITLES.get(gen_name, gen_name)} · {GRADE_RU[theta_to_grade(b)]}",
                "body": f"Шаблон {gen_name} для {scenario.spec_name}",
                "template_params": {"generator": gen_name, "params": {}},
                "a": a, "b": b, "c": c,
            })
            i += 1
    return templates


SKILLS_CATALOG = ['1с', '1с:зуп', 'a/b-тесты', 'airbyte', 'airflow', 'allure', 'amazon s3', 'ansible', 'apache', 'api gateways', 'asp.net', 'aws', 'babel', 'bash', 'bitbucket', 'bootstrap', 'c#', 'c&b', 'c++', 'cassandra', 'catboost', 'celery', 'chart.js', 'ci/cd', 'circleci', 'clickhouse', 'clojure', 'confluence', 'couchdb', 'crontab', 'css', 'cypress', 'dart', 'datadog', 'django', 'docker', 'docker compose', 'dvc', 'elasticsearch', 'elixir', 'ember.js', 'erlang', 'etl', 'excel', 'f#', 'fastapi', 'fastify', 'figma', 'firebase', 'flask', 'flutter', 'fortran', 'gcp', 'gin', 'git', 'github', 'github actions', 'gitlab', 'gitlab ci', 'go', 'google sheets', 'grafana', 'graphql', 'grpc', 'haproxy', 'haskell', 'helm', 'hugging face', 'hypothesis', 'ios', 'jasmine', 'java', 'javascript', 'jenkins', 'jest', 'jira', 'jmeter', 'jquery', 'json', 'jupyter', 'jwt', 'kafka', 'kaspressel', 'keras', 'kotlin', 'kubernetes', 'laravel', 'less', 'lightgbm', 'linux', 'looker', 'lua', 'material ui', 'matlab', 'metabase', 'microsoft sql', 'mlflow', 'mobx', 'mocha', 'mongodb', 'msk queue', 'mysql', 'nats', 'neo4j', 'nest.js', 'netlify', 'nginx', 'nifi', 'nltk', 'node.js', 'nomad', 'numpy', 'nuxt.js', 'oauth2', 'onnx', 'openai api', 'opencv', 'oracle', 'pandas', 'perl', 'php', 'playwright', 'plotly', 'postgres', 'postman', 'power bi', 'powershell', 'prisma', 'prometheus', 'puppeteer', 'pwa', 'pycaret', 'pydantic', 'pytest', 'pytorch', 'qase', 'rabbitmq', 'rails', 'rancher', 'react', 'react native', 'redis', 'redux', 'rest api', 'rnn/lstm', 'ruby', 'rust', 'sass', 'scala', 'scikit-learn', 'scipy', 'selenium', 'sendgrid', 'sentri', 'sentry', 'sequel pro', 'sinatra', 'sklearn', 'socket.io', 'solidity', 'spacy', 'spark', 'spring', 'sql', 'sqlalchemy', 'sqlite', 'storybook', 'stripe', 'superset', 'svelte', 'svg', 'swift', 'swift ui', 'symfony', 'tableau', 'tailwind', 'tensorflow', 'terraform', 'terragrunt', 'testrail', 'three.js', 'tk рф', 'torch', 'triton', 'typescript', 'vite', 'vk cloud', 'vue', 'wandb', 'wasm', 'webpack', 'websocket', 'xamarin', 'xgboost', 'yandex cloud', 'yandex tracker', 'yii', 'zabbix', 'zend', 'zig', 'автотесты', 'адаптивность', 'алгоритмы', 'аналитика', 'архивное дело', 'безопасность api', 'блокчейн', 'бухгалтерия', 'видеоаналитика', 'визуализация', 'вёрстка', 'дашборды', 'делопроизводство', 'денормализация', 'доверенность эцп', 'журналирование', 'интеграционные тесты', 'интервьюирование', 'кадровое делопроизводство', 'кэширование', 'линейная алгебра', 'микросервисы', 'многопоточность', 'мониторинг', 'нагрузочное тестирование', 'номенклатура дел', 'онбординг', 'ооп', 'паттерны проектирования', 'рекрутмент', 'рефакторинг', 'сэд', 'тест-дизайн', 'тестирование api', 'электронная очередь', 'электронная подпись']


UNIVERSAL_GENERATORS = {"code_output": 4, "string_algo": 2, "sql_select": 2, "loop_complexity": 2}


def universal_scenario(name: str) -> Scenario:
    """Сценарий для вписанного работодателем направления: универсальные шаблоны."""
    return Scenario(
        spec_code=name.lower().strip()[:32],
        spec_name=name.strip(),
        spec_description="Направление, заданное работодателем",
        survey_options=[],
        generators=UNIVERSAL_GENERATORS,
    )


GEN_TITLES = {
    "loop_complexity": "Оценка сложности кода",
    "code_output": "Что выведет код",
    "sql_select": "Работа с SQL",
    "string_algo": "Анализ строк",
    "ml_theory": "Теория машинного обучения",
    "ml_metric_calc": "Расчёт ML-метрик",
    "hr_labor_code": "Трудовое право",
    "office_records": "Делопроизводство",
    "qa_design": "Тест-дизайн",
    "analytics_metric": "Продуктовые метрики",
    "frontend_react": "React",
}
