import os
import time
from datetime import datetime
import pytesseract
from playwright.sync_api import sync_playwright
from PIL import Image
from config import TESSERACT_PATH
from image_processor import preprocess_captcha

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

def check_osago_via_nsis(search_type, query_value):
    with sync_playwright() as p:
        print("🤖 Запускаю встроенный браузер...")
        launch_args = ["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-setuid-sandbox"]
        
        try:
            browser = p.chromium.launch(headless=True, channel="chrome", args=launch_args)
        except Exception:
            try:
                browser = p.chromium.launch(headless=True, channel="msedge", args=launch_args)
            except Exception as e:
                return f"❌ Ошибка запуска браузера: {e}"

        context = browser.new_context(
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1400, "height": 1000}
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print("🤖 Перехожу на сайт НСИС...")
        try:
            page.goto("https://nsis.ru/products/osago/check/", timeout=60000, wait_until="networkidle")
            page.wait_for_timeout(4000)
        except Exception as e:
            browser.close()
            return f"❌ Сайт НСИС не ответил вовремя. ({e})"

        # ===== РАСПОЗНАВАНИЕ КАПЧИ =====
        captcha_text = ""
        max_attempts = 5
        
        for attempt in range(1, max_attempts + 1):
            print(f"🔍 Ищу капчу (Попытка {attempt} из {max_attempts})...")
            
            try:
                page.wait_for_selector('[data-js-nsis-captcha]', timeout=15000)
                page.wait_for_timeout(2000)
                
                captcha_img = page.query_selector('[data-js-nsis-captcha] img')
                if not captcha_img:
                    captcha_img = page.query_selector('img[src*="captcha"], img[alt*="Капча"]')
            except Exception:
                captcha_img = None

            if not captcha_img:
                browser.close()
                return "❌ Не удалось найти капчу на странице сайта."

            captcha_path = "captcha_temp.png"
            try:
                captcha_img.screenshot(path=captcha_path)
            except Exception as e:
                browser.close()
                return f"❌ Ошибка скриншота капчи: {e}"
                
            processed_path = preprocess_captcha(captcha_path)

            try:
                img = Image.open(processed_path)
                configs = [
                    r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789',
                    r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789',
                    r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789'
                ]
                
                best_text = ""
                for config in configs:
                    raw_text = pytesseract.image_to_string(img, config=config).strip()
                    digits_only = ''.join(filter(str.isdigit, raw_text))
                    if len(digits_only) >= len(best_text):
                        best_text = digits_only
                        
                img.close()
                
                if os.path.exists(captcha_path): os.remove(captcha_path)
                if os.path.exists(processed_path) and processed_path != captcha_path: os.remove(processed_path)
                
                if len(best_text) > 7:
                    best_text = best_text[-7:]
                elif len(best_text) < 6:
                    best_text = ""
                    
                captcha_text = best_text
                print(f"📝 Tesseract распознал: '{captcha_text}' (длина: {len(captcha_text)})")
                
            except Exception as e:
                browser.close()
                return f"❌ Ошибка Tesseract: {e}"

            if len(captcha_text) in [6, 7]:
                print(f"✅ Капча успешно распознана: {captcha_text}")
                break
            else:
                print(f"⚠️ Текст капчи не подходит. Обновляю картинку...")
                try:
                    refresh_btn = page.query_selector('[data-js-nsis-captcha] button, button:has-text("Обновить")')
                    if refresh_btn:
                        refresh_btn.click()
                        page.wait_for_timeout(2500)
                    else:
                        page.reload()
                        page.wait_for_timeout(4000)
                except Exception:
                    page.reload()
                    page.wait_for_timeout(4000)
                captcha_text = ""

        if not captcha_text or len(captcha_text) not in [6, 7]:
            browser.close()
            return f"❌ Робот не смог распознать капчу после {max_attempts} попыток (результат: '{captcha_text}'). Попробуйте еще раз."

        # ===== ЗАПОЛНЕНИЕ ФОРМЫ =====
        try:
            print("⌨️ Заполняю форму (метод из расширения)...")
            
            fill_script = """
            (args) => {
                // Распаковываем аргументы из переданного объекта
                const { searchType, queryValue, captchaWord } = args;
                
                const oldSiteResults = document.querySelector('.result-container, [class*="result"], table');
                if (oldSiteResults) oldSiteResults.remove();

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

                // Ищем все видимые input (без type="hidden")
                const allInputs = Array.from(document.querySelectorAll('input:not([type="hidden"])'));
                
                const regInput = allInputs.find(i => i.placeholder?.toLowerCase().includes('гос') || i.id?.toLowerCase().includes('reg') || i.name?.toLowerCase().includes('reg'));
                const vinInput = allInputs.find(i => i.placeholder?.toLowerCase().includes('vin') || i.id?.toLowerCase().includes('vin') || i.name?.toLowerCase().includes('vin'));
                const bodyInput = allInputs.find(i => i.placeholder?.toLowerCase().includes('кузов') || i.id?.toLowerCase().includes('body') || i.name?.toLowerCase().includes('body'));
                const captchaInputEl = allInputs.find(i => i.placeholder?.toLowerCase().includes('картинки') || i.id?.toLowerCase().includes('captcha') || i.name?.toLowerCase().includes('captcha'));
                const dateInput = allInputs.find(i => i.placeholder?.toLowerCase().includes('дату') || i.id?.toLowerCase().includes('date') || i.name?.toLowerCase().includes('date'));

                if (regInput) simulateKeyboardType(regInput, '');
                if (vinInput) simulateKeyboardType(vinInput, '');
                if (bodyInput) simulateKeyboardType(bodyInput, '');

                let fieldFilled = false;
                if (searchType === 'vin' && vinInput) {
                    simulateKeyboardType(vinInput, queryValue);
                    fieldFilled = true;
                } else if ((searchType === 'reg' || searchType === 'regNumber') && regInput) {
                    simulateKeyboardType(regInput, queryValue);
                    fieldFilled = true;
                } else if ((searchType === 'body' || searchType === 'bodyNumber') && bodyInput) {
                    simulateKeyboardType(bodyInput, queryValue);
                    fieldFilled = true;
                }

                if (dateInput) {
                    const today = new Date();
                    const dd = String(today.getDate()).padStart(2, '0');
                    const mm = String(today.getMonth() + 1).padStart(2, '0');
                    const yyyy = today.getFullYear();
                    simulateKeyboardType(dateInput, `${dd}.${mm}.${yyyy}`);
                }

                let captchaFilled = false;
                if (captchaInputEl) {
                    simulateKeyboardType(captchaInputEl, captchaWord);
                    captchaFilled = true;
                }

                setTimeout(() => {
                    const submitBtn = document.querySelector('button[type="submit"]') || 
                                      Array.from(document.querySelectorAll('button')).find(b => b.innerText?.includes('Отправить') || b.innerText?.includes('Проверить'));
                    if (submitBtn) {
                        submitBtn.focus();
                        submitBtn.click();
                    }
                }, 600);

                return { fieldFilled, captchaFilled };
            }
            """
            
            # ИСПРАВЛЕНИЕ: Передаем все аргументы ВНУТРИ ОДНОГО СЛОВАРЯ
            args_dict = {
                "searchType": search_type, 
                "queryValue": query_value, 
                "captchaWord": captcha_text
            }
            result = page.evaluate(fill_script, args_dict)
            
            if not result.get('fieldFilled'):
                browser.close()
                return "❌ Не удалось найти и заполнить поле для ввода данных."
            if not result.get('captchaFilled'):
                browser.close()
                return "❌ Не удалось найти поле для ввода капчи."
                
            print(f"  ✅ Поля успешно заполнены методом расширения")
            print(f"  ✅ Кнопка 'Отправить' нажата")
                
        except Exception as e:
            browser.close()
            return f"❌ Ошибка заполнения формы: {e}"

        # ===== ОЖИДАНИЕ РЕЗУЛЬТАТА =====
        print("⏱ Ожидаю ответ от базы данных...")
        
        for attempt in range(40):
            time.sleep(0.5)
            
            try:
                check_script = """
                () => {
                    const bodyText = document.body.innerText;
                    const modal = document.querySelector('[class*="modal"], [class*="dialog"], [role="dialog"]');
                    const modalText = modal ? modal.innerText : '';
                    
                    if (modalText.includes("попробуйте еще раз") || bodyText.includes("попробуйте еще раз") ||
                        modalText.includes("попробуйте ещё раз") || bodyText.includes("попробуйте ещё раз")) {
                        return { status: "server_error" };
                    }
                    if (bodyText.includes("Неверный код") || bodyText.includes("Капча введена неверно") || bodyText.includes("неверно")) {
                        return { status: "captcha_error" };
                    }
                    
                    const hasResultCards = document.querySelector('.result-container, [class*="Card"], [class*="Result"], main');
                    if (hasResultCards && (bodyText.includes("Данные о полисах ОСАГО") || bodyText.includes("Статус договора") || bodyText.includes("Серия полиса"))) {
                        return { status: "success", text: hasResultCards.innerText };
                    }
                    
                    if (bodyText.includes("не найден") || bodyText.includes("Полис отсутствует") || bodyText.includes("Ничего не найдено")) {
                        return { status: "not_found" };
                    }
                    return { status: "waiting" };
                }
                """
                res = page.evaluate(check_script)
                
                if res['status'] == "captcha_error":
                    browser.close()
                    return f"❌ Капча введена неверно ({captcha_text}). Попробуйте ещё раз!"
                elif res['status'] == "server_error":
                    browser.close()
                    return "⚠️ Сервер НСИС перегружен. Повторите запрос."
                elif res['status'] == "success":
                    browser.close()
                    text = res['text']
                    lines = [line.strip() for line in text.split('\n') if line.strip()]
                    return f"✅ Полис найден:\n\n" + '\n'.join(lines[:25])
                elif res['status'] == "not_found":
                    browser.close()
                    return "⚠️ Страховка ОСАГО не найдена в базе НСИС."
                    
            except Exception:
                continue
        
        browser.close()
        return "⏱ Время ожидания истекло."