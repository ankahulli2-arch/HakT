
import random
import sys
import time

import httpx

BASE = "http://localhost:8000/api"
rng = random.Random(7)
stamp = int(time.time() * 1000) % 10**9
c = httpx.Client(timeout=30)
fails = []

def step(name, cond, extra=""):
    mark = "OK " if cond else "FAIL"
    print(f"[{mark}] {name} {extra}")
    if not cond:
        fails.append(name)

email = f"e2e_cand_{stamp}@example.ru"
r = c.post(f"{BASE}/auth/register", json={"email": email, "password": "Passw0rd123",
                                          "role": "candidate"})
step("регистрация кандидата", r.status_code == 201, r.text[:80])
code = r.json()["confirm_code_mvp"]
r = c.post(f"{BASE}/auth/confirm", json={"email": email, "code": code})
step("подтверждение email", r.status_code == 200)
tok = r.json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}

r = c.put(f"{BASE}/candidate/profile", headers=H,
          json={"full_name": "Тест Кандидатов", "contacts": {"telegram": "@e2e"},
                "summary": "Python бэкенд", "stack": ["python", "fastapi", "postgresql"],
                "experience_years": 2.5, "soft_skills": ["командная работа"]})
step("профиль заполнен", r.status_code == 200)

r = c.put(f"{BASE}/candidate/privacy", headers=H,
          params={"is_public": "true", "consent": "true"})
step("согласие на обработку данных", r.status_code == 200)

r = c.get(f"{BASE}/testing/specializations")
step("справочник специализаций", r.status_code == 200 and len(r.json()) >= 8)
r = c.post(f"{BASE}/testing/survey", headers=H,
           json={"specialization_code": "backend", "survey_answer": "Веб-разработка",
                 "target_grade": "middle"})
step("опрос → старт теста", r.status_code == 200, str(r.json().get("session_id", ""))[:8])

answers = 0
while True:
    item = r.json().get("next_item") or (r.json().get("first_item") if answers == 0 else None)
    if item is None:
        break
    payload = {"item_id": item["item_id"]}
    if item.get("options"):
        payload["choice"] = rng.randint(0, len(item["options"]) - 1)
    else:
        payload["value"] = "42"
    r = c.post(f"{BASE}/testing/answer", headers=H, json=payload)
    answers += 1
    if r.status_code != 200 or r.json().get("finished"):
        break
    if answers > 25:
        break
step(f"адаптивный тест завершён ({answers} заданий)", r.json().get("finished") is True,
     f"θ={r.json().get('theta')}, уровень={r.json().get('applied_grade')}")

r = c.get(f"{BASE}/testing/status", headers=H)
step("категория присвоена", r.json().get("category") is not None, r.json().get("category", ""))


r = c.post(f"{BASE}/fsp/link/FSP-2026-0001", headers=H)
step("связь с ФСП ID", r.json().get("linked") is True, f"fsp_index={r.json().get('fsp_index')}")
r = c.post(f"{BASE}/fsp/link/FSP-404-404", headers=H)
step("нет истории ФСП — корректно", r.json().get("linked") is False)


email2 = f"e2e_emp_{stamp}@example.ru"
r = c.post(f"{BASE}/auth/register", json={"email": email2, "password": "Passw0rd123",
                                          "role": "employer"})
code2 = r.json()["confirm_code_mvp"]
r = c.post(f"{BASE}/auth/confirm", json={"email": email2, "code": code2})
tok2 = r.json()["access_token"]
H2 = {"Authorization": f"Bearer {tok2}"}

r = c.put(f"{BASE}/employer/profile", headers=H2,
          json={"company_name": "E2E Компания", "description": "Тестовая",
                "industry": "ИТ", "contact_email": email2, "contact_phone": ""})
step("профиль работодателя", r.status_code == 200)

r = c.post(f"{BASE}/matching/need", headers=H2, json={
    "raw_text": "Нужен бэкенд-разработчик middle: python, fastapi, postgresql, docker",
})
need = r.json()
step("потребность → подборка", r.status_code == 200 and len(need["items"]) > 0,
     f"{len(need['items'])} кандидатов за {need['elapsed_ms']} мс")
top = need["items"][0]
step("выдача объяснима", "breakdown" in top and "rationale" in top,
     top["rationale"][:70])
step("контакты скрыты", "candidate_contacts" not in top or top.get("candidate_contacts") is None)


r = c.post(f"{BASE}/employer/tests/draft", headers=H2, json={
    "specialization_code": "backend",
    "raw_text": "Ищем бэкенд-разработчика python fastapi postgresql redis docker kubernetes",
    "use_web": True,
})
bp = r.json()
step("черновик из интернета", r.status_code == 201 and len(bp["items"]) >= 5,
     f"навыков найдено: {len(bp['researched_skills'])}; источники: {bp['researched_skills'] and ''}"
     f"{'' if not bp.get('note') else ''}")
bid = bp["blueprint_id"]

r = c.post(f"{BASE}/employer/tests/{bid}/items", headers=H2, json={
    "title": "Наш вопрос", "body": "Сколько будет 2+2?",
    "options": ["3", "4", "5"], "correct": "4"})
step("свой вопрос добавлен", r.status_code == 201)
r = c.delete(f"{BASE}/employer/tests/{bid}/items/{bp['items'][0]['ref_id']}", headers=H2)
step("вопрос удалён из черновика", r.status_code == 200, f"осталось {r.json()['items_count']}")
r = c.post(f"{BASE}/employer/tests/{bid}/publish", headers=H2)
step("тест опубликован", r.status_code == 200 and r.json()["status"] == "published")

r = c.get(f"{BASE}/candidate/profile", headers=H)
my_cand_id = r.json()["user_id"]
step("id кандидата", bool(my_cand_id))


r = c.post(f"{BASE}/vacancies", headers=H2, json={
    "title": "E2E бэкенд-вакансия", "description": "Разработка API",
    "specialization_code": "backend", "min_grade": "junior",
    "stack": ["python"], "salary_min": 150000, "salary_max": 250000})
vac = r.json()
step("работодатель публикует вакансию", r.status_code == 201)

r = c.post(f"{BASE}/invitations", headers=H2, json={
    "candidate_id": my_cand_id, "vacancy_id": vac["id"], "blueprint_id": bid,
    "message": "Приглашаем на позицию, нам подходит ваш профиль",
    "salary_min": 180000, "salary_max": 300000})
step("приглашение отправлено", r.status_code == 201, r.text[:60])
inv_id = r.json()["id"]

r = c.get(f"{BASE}/candidate/invitations", headers=H)
mine_inv = next((i for i in r.json() if i["id"] == inv_id), None)
step("кандидат видит приглашение и вилку", mine_inv is not None
     and mine_inv["salary_min"] == 180000)

r = c.post(f"{BASE}/testing/start-by-invitation/{inv_id}", headers=H,
           params={"target_grade": "middle"})
step("старт авторского теста", r.status_code == 200, str(r.json().get("session_id", ""))[:8])

item = r.json().get("next_item") or r.json().get("first_item")
for _ in range(30):
    if item is None:
        break
    payload = {"item_id": item["item_id"]}
    if item.get("options"):
        payload["choice"] = 0
    else:
        payload["value"] = "4"
    r = c.post(f"{BASE}/testing/answer", headers=H, json=payload)
    if r.json().get("finished"):
        break
    item = r.json().get("next_item")
step("авторский тест пройден", r.json().get("finished") is True)

r = c.post(f"{BASE}/candidate/invitations/{inv_id}/decide", headers=H,
           params={"accept": "true"})
step("приглашение принято", r.json().get("status") == "accepted")

r = c.get(f"{BASE}/employer/invitations", headers=H2)
mine = next(i for i in r.json() if i["id"] == inv_id)
step("контакты раскрыты после принятия", mine["candidate_contacts"] is not None,
     str(mine["candidate_contacts"])[:50])


r = c.post(f"{BASE}/applications", headers=H, params={"vacancy_id": vac["id"]},
           json={"cover_letter": "Хочу к вам"})
step("отклик отправлен", r.status_code == 201)

r = c.get(f"{BASE}/employer/vacancies", headers=H2)
step("работодатель видит отклики", any(len(v.get("applications", [])) > 0 for v in r.json()))

for v in r.json():
    if v.get("title", "").startswith("E2E"):
        c.delete(f"{BASE}/vacancies/{v['id']}", headers=H2)


r = c.post(f"{BASE}/demo/quiz/start", params={"spec": "backend"})
step("демо-квиз запустился без регистрации", r.status_code == 200 and r.json().get("item"),
     str(r.json().get("item", {}).get("title", ""))[:40])
if r.status_code == 200:
    dtok = r.json()["token"]; ditem = r.json()["item"]; dfinal = {}
    for _ in range(6):
        ap = {"token": dtok, "item_id": ditem["id"]}
        if ditem.get("answer_type") == "choice":
            ap["choice"] = rng.randint(0, max(0, len(ditem.get("options", [])) - 1))
        else:
            ap["value"] = "42"
        r = c.post(f"{BASE}/demo/quiz/answer", json=ap)
        dfinal = r.json()
        if dfinal.get("finished") or not dfinal.get("next_item"):
            break
        ditem = dfinal["next_item"]
    step("демо-квиз адаптируется и даёт балл", dfinal.get("finished") is True
         and "score" in dfinal, f"score={dfinal.get('score')} θ={dfinal.get('theta')}")

r = c.get(f"{BASE}/leaderboard/backend")
step("лидерборд категории (Redis)", r.status_code == 200 and len(r.json().get("items", [])) > 0,
     f"{len(r.json().get('items', []))} в топе")

r = c.get(f"{BASE}/candidate/certificate.pdf", headers=H)
step("PDF-сертификат категории", r.status_code == 200 and r.content[:4] == b"%PDF",
     r.text[:60] if r.status_code != 200 else "")

r = c.get(f"{BASE}/verify/{my_cand_id}/" + "0" * 64)
step("verify отклоняет поддельную подпись", r.status_code == 200 and r.json().get("valid") is False)

r = c.put(f"{BASE}/employer/blind", headers=H2, params={"enabled": "true"})
step("слепой найм включён", r.status_code == 200 and r.json().get("blind_mode") is True)
r = c.post(f"{BASE}/matching/need", headers=H2, json={
    "raw_text": "бэкенд python fastapi middle"})
bl = r.json().get("items", [])
step("слепой найм скрывает имена", len(bl) > 0
     and all(i["full_name"].startswith("Кандидат №") for i in bl),
     bl[0]["full_name"] if bl else "нет кандидатов")
c.put(f"{BASE}/employer/blind", headers=H2, params={"enabled": "false"})

r = c.get(f"{BASE}/employer/funnel", headers=H2)
step("воронка найма", r.status_code == 200 and "applications" in r.json()
     and "invited" in r.json(), f"{r.json().get('vacancies')} в. {r.json().get('applications')} о. "
     f"{r.json().get('invited')} п. {r.json().get('accepted')} пр.")

print()
print("ИТОГ:", "ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ" if not fails else f"ПРОВАЛЕНО: {fails}")
sys.exit(1 if fails else 0)
