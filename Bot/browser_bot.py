import os
import time
from collections import Counter
from datetime import datetime
from urllib.parse import urlparse
import pytesseract
from playwright.sync_api import sync_playwright
from PIL import Image, ImageEnhance, ImageOps
from config import TESSERACT_PATH

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

# ===== НАСТРОЙКИ =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHOW_BROWSER = False   # False = браузер скрыт за экраном
SLOW_MO = 0            # Без замедлений
KEEP_WINDOW_SEC = 0    # Не держать окно после результата
MAX_SUBMITS = 5
ALLOW_MANUAL = True    # Ручной ввод капчи через консоль — как страховка
MANUAL_ONLY = False
AUTO_TRIES = 3

def find_yandex_browser():
    candidates = [
        os.path.expandvars(r"%LOCALAPPDATA%\Yandex\YandexBrowser\Application\browser.exe"),
        r"C:\Program Files (x86)\Yandex\YandexBrowser\Application\browser.exe",
        r"C:\Program Files\Yandex\YandexBrowser\Application\browser.exe",
    ]
    try:
        user = os.getlogin()
        candidates.insert(0, rf"C:\Users\{user}\AppData\Local\Yandex\YandexBrowser\Application\browser.exe")
    except Exception:
        pass
    for path in candidates:
        if os.path.exists(path):
            return path
    return None

def launch_browser(p):
    """Запуск браузера с постоянным профилем, окно скрыто за экраном"""
    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--no-first-run",
        "--no-default-browser-check",
        "--hide-restore-bubble",
        "--window-position=-32000,-32000",  # окно за пределами экрана
        "--window-size=1400,1000",
    ]
    slow_mo = SLOW_MO if SHOW_BROWSER else 0

    variants = [
        ("yandex", find_yandex_browser(), os.path.join(BASE_DIR, "profile_yandex")),
        ("chrome", None, os.path.join(BASE_DIR, "profile_chrome")),
        ("msedge", None, os.path.join(BASE_DIR, "profile_edge")),
    ]
    for name, exe, prof in variants:
        if name == "yandex" and not exe:
            continue
        try:
            kwargs = dict(
                headless=False, args=launch_args, slow_mo=slow_mo,
                ignore_https_errors=True, viewport={"width": 1400, "height": 1000},
            )
            if exe:
                kwargs["executable_path"] = exe
            else:
                kwargs["channel"] = name
            ctx = p.chromium.launch_persistent_context(user_data_dir=prof, **kwargs)
            print(f"✅ Браузер запущен в фоне: {name}")
            return ctx
        except Exception as e:
            print(f"⚠️ Не удалось запустить {name}: {e}")
    return None

def ask_manual_captcha():
    print("\n" + "=" * 62)
    print("🖐 РУЧНОЙ РЕЖИМ: бот не смог распознать капчу.")
    print("   (браузер скрыт — временно откройте папку проекта,")
    print("    файл captcha_temp.png содержит последнюю картинку капчи)")
    code = input("➡️  Введите цифры капчи в консоли и нажмите Enter: ").strip()
    print("=" * 62 + "\n")
    return ''.join(filter(str.isdigit, code))

def recognize_captcha_digits(path):
    """Tesseract-ансамбль: несколько вариантов обработки, голосование"""
    try:
        base = Image.open(path).convert('L')
        base = base.resize((base.width * 4, base.height * 4), Image.Resampling.LANCZOS)
        variants = [
            ImageEnhance.Contrast(base).enhance(2.0),
            ImageEnhance.Contrast(base).enhance(3.0),
            ImageOps.autocontrast(base),
        ]
        candidates = []
        for var in variants:
            for psm in ('7', '8', '6'):
                txt = pytesseract.image_to_string(
                    var, config=f'--oem 3 --psm {psm} -c tessedit_char_whitelist=0123456789'
                ).strip()
                digits = ''.join(filter(str.isdigit, txt))
                if len(digits) > 7:
                    digits = digits[-7:]
                if 6 <= len(digits) <= 7:
                    candidates.append(digits)
        if not candidates:
            return "", 0
        best, votes = Counter(candidates).most_common(1)[0]
        return best, votes
    except Exception as e:
        print(f"⚠️ Ошибка OCR: {e}")
        return "", 0

def format_policy_report(raw):
    """Превращает текст модалки НСИС в читаемый отчёт 'метка: значение'"""
    lines = [l.strip() for l in raw.split('\n') if l.strip()]
    out = []
    buf = None
    for line in lines:
        if buf is not None:
            out.append(buf + " " + line)
            buf = None
        elif line.endswith(':') or line.endswith(':'):
            buf = line.rstrip(':') + ":"
        else:
            out.append(line)
    if buf is not None:
        out.append(buf)
    start = 0
    for idx, l in enumerate(out):
        if l.startswith("Серия полиса"):
            start = idx
            break
    return '\n'.join(out[start:]) if out else raw

def check_osago_via_nsis(search_type, query_value):
    with sync_playwright() as p:
        print("🤖 Запускаю браузер (скрытый режим)...")
        context = launch_browser(p)
        if context is None:
            return "❌ Ошибка запуска браузера"

        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        def log_response(resp):
            host = urlparse(resp.url).netloc
            if resp.request.method == "POST" and host.endswith("nsis.ru"):
                print(f"🌐 POST {resp.url.split('?')[0]} -> {resp.status}")
        page.on("response", log_response)

        # ===== ЗАГРУЗКА СТРАНИЦЫ =====
        print("🤖 Перехожу на сайт НСИС...")
        loaded = False
        for attempt in range(1, 4):
            try:
                if attempt == 1:
                    page.goto("https://nsis.ru/products/osago/check/", timeout=60000, wait_until="domcontentloaded")
                else:
                    print(f"🔄 Повторная загрузка страницы (попытка {attempt})...")
                    page.reload(timeout=60000, wait_until="domcontentloaded")
                page.wait_for_selector('[data-js-nsis-captcha], form[data-js-form]', timeout=30000)
                page.wait_for_timeout(2000)
                loaded = True
                break
            except Exception as e:
                print(f"⚠️ Загрузка не удалась (попытка {attempt}): {e}")
        if not loaded:
            context.close()
            return "❌ Сайт НСИС не ответил вовремя (3 попытки). Попробуйте еще раз."

        # Закрываем cookie-баннер
        try:
            cookie_btn = page.query_selector('button[data-js-disclaimerAccept]')
            if cookie_btn:
                cookie_btn.click()
                page.wait_for_timeout(800)
        except Exception:
            pass
        try:
            page.evaluate("() => { const d = document.getElementById('cookieDisclaimer'); if (d) d.remove(); }")
        except Exception:
            pass

        # ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
        def screenshot_captcha():
            img = page.query_selector('[data-js-nsis-captcha] img') or page.query_selector('img[src*="captcha"]')
            if not img:
                return None
            try:
                page.evaluate("""() => {
                    const img = document.querySelector('[data-js-nsis-captcha] img') || document.querySelector('img[src*="captcha"]');
                    if (img) img.scrollIntoView({block: 'center', inline: 'nearest'});
                }""")
                page.wait_for_timeout(500)
            except Exception:
                pass
            for _ in range(10):
                ready = page.evaluate("""() => {
                    const img = document.querySelector('[data-js-nsis-captcha] img') || document.querySelector('img[src*="captcha"]');
                    return img ? (img.complete && img.naturalWidth > 0) : false;
                }""")
                if ready:
                    break
                page.wait_for_timeout(400)
            path = os.path.join(BASE_DIR, "captcha_temp.png")
            img.screenshot(path=path)
            return path

        def refresh_captcha():
            btn = page.query_selector('[data-js-nsis-captcha] button') or page.query_selector('button:has-text("Обновить")')
            if btn:
                btn.click()
            else:
                page.reload()
                page.wait_for_timeout(3000)
            page.wait_for_timeout(2000)

        def fill_captcha_by_keyboard(code):
            cap = page.query_selector('[data-js-nsis-captcha] input:not([type="hidden"])') or page.query_selector('[data-js-nsis-captcha] input')
            if not cap:
                print("  ❌ Поле капчи не найдено!")
                return False
            cap.click()
            page.keyboard.press('Control+a')
            page.keyboard.type(code, delay=80)
            page.wait_for_timeout(300)
            actual = cap.input_value()
            if actual != code:
                page.evaluate("""(code) => {
                    const inp = document.querySelector('[data-js-nsis-captcha] input:not([type="hidden"])') || document.querySelector('[data-js-nsis-captcha] input');
                    if (!inp) return;
                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    setter.call(inp, code);
                    inp.dispatchEvent(new Event('input', { bubbles: true }));
                    inp.dispatchEvent(new Event('change', { bubbles: true }));
                }""", code)
                page.wait_for_timeout(300)
                actual = cap.input_value()
            print(f"  🔢 Капча: введено '{code}', в поле лежит '{actual}'")
            return actual == code

        def fill_main_fields():
            fill_script = """
            (args) => {
                const { searchType, queryValue } = args;
                const simulateKeyboardType = (input, text) => {
                    if (!input) return false;
                    input.focus();
                    input.value = '';
                    input.value = text;
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                    input.dispatchEvent(new Event('blur', { bubbles: true }));
                    return true;
                };
                const allInputs = Array.from(document.querySelectorAll('input:not([type="hidden"])'));
                const regInput = allInputs.find(i => i.placeholder?.toLowerCase().includes('гос') || i.id?.toLowerCase().includes('reg') || i.name?.toLowerCase().includes('reg'));
                const vinInput = allInputs.find(i => i.placeholder?.toLowerCase().includes('vin') || i.id?.toLowerCase().includes('vin') || i.name?.toLowerCase().includes('vin'));
                const bodyInput = allInputs.find(i => i.placeholder?.toLowerCase().includes('кузов') || i.id?.toLowerCase().includes('body') || i.name?.toLowerCase().includes('body'));

                if (regInput) simulateKeyboardType(regInput, '');
                if (vinInput) simulateKeyboardType(vinInput, '');
                if (bodyInput) simulateKeyboardType(bodyInput, '');

                let fieldFilled = false;
                let filledValue = null;
                if (searchType === 'vin' && vinInput) { simulateKeyboardType(vinInput, queryValue); fieldFilled = true; filledValue = vinInput.value; }
                else if (searchType === 'reg' && regInput) { simulateKeyboardType(regInput, queryValue); fieldFilled = true; filledValue = regInput.value; }
                else if (searchType === 'body' && bodyInput) { simulateKeyboardType(bodyInput, queryValue); fieldFilled = true; filledValue = bodyInput.value; }
                return { fieldFilled, filledValue };
            }
            """
            return page.evaluate(fill_script, {"searchType": search_type, "queryValue": query_value})

        def click_submit():
            page.evaluate("""() => {
                const b = document.querySelector('.tabs__contentItem.isActive button[type="submit"]') || document.querySelector('button[type="submit"]');
                if (b) { b.focus(); b.click(); }
            }""")

        def wait_result():
            for _ in range(50):
                time.sleep(0.5)
                try:
                    res = page.evaluate("""
                    () => {
                        const bodyText = document.body.innerText;
                        const modal = document.querySelector('[class*="modal"], [class*="Modal"], [class*="dialog"], [class*="Dialog"], [role="dialog"]');
                        const modalText = modal ? modal.innerText : '';

                        const MARKER = "Данные о полисах ОСАГО";
                        if (bodyText.includes(MARKER) || modalText.includes(MARKER)) {
                            let best = null;
                            const nodes = document.querySelectorAll('div, section, dialog, [role="dialog"]');
                            for (const el of nodes) {
                                const t = el.innerText || '';
                                if (t.includes(MARKER) && t.includes("Серия полиса")) {
                                    if (!best || t.length < best.innerText.length) best = el;
                                }
                            }
                            if (!best) {
                                for (const el of nodes) {
                                    const t = el.innerText || '';
                                    if (t.includes(MARKER) && t.length > 150) {
                                        if (!best || t.length < best.innerText.length) best = el;
                                    }
                                }
                            }
                            return { status: "success", text: best ? best.innerText : bodyText };
                        }
                        if (modalText.includes("Проверка на робота не пройдена") || modalText.includes("Неверный код") ||
                            modalText.includes("Капча введена неверно") || bodyText.includes("Капча введена неверно")) {
                            return { status: "captcha_error" };
                        }
                        if (modalText.includes("попробуйте еще раз") || modalText.includes("попробуйте ещё раз") ||
                            bodyText.includes("пике активности")) {
                            return { status: "server_error" };
                        }
                        if (modalText.includes("не найден") || modalText.includes("Полис отсутствует") || bodyText.includes("Полис отсутствует")) {
                            return { status: "not_found" };
                        }
                        return { status: "waiting" };
                    }
                    """)
                    if res['status'] != "waiting":
                        return res
                except Exception:
                    continue
            return {"status": "timeout"}

        # ===== ОСНОВНОЙ ЦИКЛ =====
        fields = fill_main_fields()
        if not fields.get('fieldFilled'):
            context.close()
            return "❌ Не удалось найти и заполнить поле для ввода данных."
        print(f"  ✅ Основное поле заполнено: {fields.get('filledValue')}")

        rejects = 0
        used_codes = set()

        for submit_attempt in range(1, MAX_SUBMITS + 1):
            print(f"📨 Отправка #{submit_attempt}...")

            captcha_text = ""

            if not MANUAL_ONLY and rejects < 2:
                for att in range(1, AUTO_TRIES + 1):
                    path = screenshot_captcha()
                    if not path:
                        context.close()
                        return "❌ Не удалось найти капчу на странице сайта."

                    code, votes = recognize_captcha_digits(path)
                    print(f"📝 Чтение {att}: '{code}' (голосов: {votes})")
                    if code:
                        used_codes.add(code)
                        captcha_text = code
                        break
                    refresh_captcha()

            if not captcha_text and ALLOW_MANUAL:
                captcha_text = ask_manual_captcha()

            if not captcha_text or len(captcha_text) not in (6, 7):
                context.close()
                return "❌ Капча не получена (введено не 6 и не 7 цифр). Попробуйте еще раз."
            print(f"✅ Капча для отправки: {captcha_text}")

            fill_captcha_by_keyboard(captcha_text)
            click_submit()
            print("  ✅ Кнопка 'Отправить' нажата")
            page.wait_for_timeout(1500)

            print("⏱ Ожидаю ответ от базы данных...")
            res = wait_result()

            if res['status'] == "success":
                report = format_policy_report(res['text'])
                print("  ✅ УСПЕХ! Данные полиса:")
                print("-" * 50)
                print(report)
                print("-" * 50)
                context.close()
                return f"✅ Полис найден:\n\n{report}"
            elif res['status'] == "captcha_error":
                rejects += 1
                used_codes.add(captcha_text)
                print(f"⚠️ Сайт отклонил капчу ({captcha_text}). Закрываю модалку...")
                try:
                    close_btn = page.query_selector('button:has-text("Закрыть")')
                    if close_btn:
                        close_btn.click()
                        page.wait_for_timeout(800)
                except Exception:
                    pass
                refresh_captcha()
                continue
            elif res['status'] == "server_error":
                context.close()
                return "⚠️ Сервер НСИС перегружен. Повторите запрос."
            elif res['status'] == "not_found":
                context.close()
                return "⚠️ Страховка ОСАГО не найдена в базе НСИС."
            else:
                print("⚠️ За эту отправку ответа не получили. Пробую еще раз...")
                refresh_captcha()
                continue

        context.close()
        return "⏱ Не удалось получить результат за несколько попыток. Попробуйте еще раз."