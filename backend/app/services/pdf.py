import os
import re
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.services.scoring import GRADE_RU

_BUNDLED_FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"


def _font_path(name: str) -> str:
    for candidate in (_BUNDLED_FONTS / name,
                      Path("/usr/share/fonts/truetype/dejavu") / name,
                      Path("C:/Windows/Fonts") / name):
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError(f"Шрифт {name} не найден")

EMAIL_RE = re.compile(r"[\w.+\-]+@[\w\-]+\.[\w.\-]+")
PHONE_RE = re.compile(r"(\+7|8)[\s\-()]?\d{3}[\s\-()]?\d{3}[\s\-()]?\d{2}[\s\-()]?\d{2}")


def generate_profile_pdf(profile, categories: list, history: list, path: str) -> str:
    pdfmetrics.registerFont(TTFont("DejaVu", _font_path("DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVuB", _font_path("DejaVuSans-Bold.ttf")))
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    y = h - 60

    c.setFont("DejaVuB", 24)
    c.drawString(50, y, profile.full_name or "Кандидат")
    y -= 26
    contacts = profile.contacts or {}
    c.setFont("DejaVu", 11)
    c.setFillColorRGB(0.36, 0.16, 0.55)
    line = " · ".join(x for x in (
        contacts.get("telegram") or "",
        contacts.get("phone") or "",
    ) if x)
    c.drawString(50, y, line)
    y -= 30

    c.setFillColorRGB(0.1, 0.1, 0.3)
    for cat in categories:
        c.setFont("DejaVuB", 14)
        c.drawString(50, y, f"Категория: {cat['category']} — балл {cat['score']} из 100, "
                            f"место {cat['rank']}-е из {cat['candidates_in_category']}")
        y -= 22

    if profile.experience_years:
        c.setFont("DejaVu", 12)
        c.drawString(50, y, f"Опыт: {profile.experience_years:g} лет")
        y -= 20

    c.setFont("DejaVuB", 14)
    c.drawString(50, y, "Навыки")
    y -= 18
    c.setFont("DejaVu", 11)
    x = 50
    for s in (profile.stack or []):
        c.setFillColorRGB(0.36, 0.16, 0.55)
        c.roundRect(x, y - 4, 12 + 6.2 * len(s), 18, 6, stroke=0, fill=1)
        c.setFillColorRGB(1, 1, 1)
        c.drawString(x + 6, y, s)
        x += 24 + 6.2 * len(s)
        if x > w - 120:
            x = 50
            y -= 24
    c.setFillColorRGB(0.1, 0.1, 0.3)
    y -= 30

    if profile.summary:
        c.setFont("DejaVuB", 14)
        c.drawString(50, y, "О себе")
        y -= 18
        c.setFont("DejaVu", 11)
        for chunk in (profile.summary or "").split("."):
            if chunk.strip():
                c.drawString(50, y, "• " + chunk.strip())
                y -= 16
        y -= 8

    if profile.fsp_history:
        c.setFont("DejaVuB", 14)
        c.drawString(50, y, "Подтверждённые достижения ФСП")
        y -= 18
        c.setFont("DejaVu", 11)
        for a in profile.fsp_history:
            c.drawString(50, y, f"• {a.get('title')} — {a.get('result')} ({a.get('level')}, {a.get('year')})")
            y -= 16
        y -= 8

    if history:
        c.setFont("DejaVuB", 14)
        c.drawString(50, y, "История тестирований")
        y -= 18
        c.setFont("DejaVu", 10.5)
        for g in history:
            for a in g["attempts"]:
                c.drawString(50, y, f"• {g['specialization']}: {a['date']} — балл {a['score']} из 100, "
                                    f"{GRADE_RU.get(a['grade'], a['grade'])}, честность {round(a['integrity'] * 100)}%")
                y -= 15
            y -= 4

    c.setFont("DejaVu", 8)
    c.setFillColorRGB(0.5, 0.5, 0.55)
    c.drawString(50, 40, "Сгенерировано платформой подбора ИТ-специалистов ФСП · балл подтверждён адаптивным тестом")
    c.save()
    return path


def generate_certificate_pdf(full_name: str, category: str, score: int,
                             specialty_name: str, verify_url: str, signature: str,
                             path: str) -> str:
    import io
    import segno
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    pdfmetrics.registerFont(TTFont("DejaVu", _font_path("DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVuB", _font_path("DejaVuSans-Bold.ttf")))
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4

    c.setFillColorRGB(0.36, 0.16, 0.55)
    c.rect(0, h - 150, w, 150, stroke=0, fill=1)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("DejaVuB", 26)
    c.drawString(50, h - 78, "Сертификат категории")
    c.setFont("DejaVu", 12)
    c.drawString(50, h - 108, specialty_name or "ИТ-специальность")
    c.drawString(50, h - 126, "Подтверждена адаптивным CAT-тестом платформы ФСП")

    c.setFillColorRGB(0.15, 0.15, 0.25)
    c.setFont("DejaVuB", 20)
    c.drawString(50, h - 210, full_name or "Кандидат")
    c.setFont("DejaVu", 15)
    c.drawString(50, h - 246, f"Категория: {category}")
    c.setFont("DejaVuB", 30)
    c.setFillColorRGB(0.36, 0.16, 0.55)
    c.drawString(50, h - 300, f"{score} из 100")
    c.setFont("DejaVu", 11)
    c.setFillColorRGB(0.3, 0.3, 0.35)
    c.drawString(50, h - 330, "Сканируйте QR — проверим подлинность категории онлайн")

    qr = segno.make(verify_url, error="m")
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=8, border=2, dark="#2a2140", light="#ffffff")
    from reportlab.lib.utils import ImageReader
    buf.seek(0)
    c.drawImage(ImageReader(buf), w - 200, 120, 150, 150)

    c.setFillColorRGB(0.5, 0.5, 0.55)
    c.setFont("DejaVu", 8)
    c.drawString(50, 70, "Подлинность подтверждается по адресу из QR-кода")
    c.drawString(50, 56, f"Проверка: {verify_url}")
    c.drawString(50, 42, f"Подпись: {signature[:32]}…")
    c.setFont("DejaVu", 8)
    c.drawString(50, 28, "Сгенерировано платформой подбора ИТ-специалистов ФСП")
    c.save()
    return path


def parse_resume_pdf(text: str, skills_catalog: list) -> dict:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    name = ""
    for l in lines[:4]:
        words = l.split()
        if 2 <= len(words) <= 4 and not EMAIL_RE.search(l) and not PHONE_RE.search(l):
            name = l
            break
    email = EMAIL_RE.search(text)
    phone = PHONE_RE.search(text)
    low = text.lower()
    stack = [s for s in skills_catalog if re.search(rf"(?<!\w){re.escape(s)}(?!\w)", low)][:20]
    return {
        "full_name": name,
        "contacts": {
            "email": email.group(0) if email else "",
            "phone": phone.group(0) if phone else "",
        },
        "stack": stack,
    }
