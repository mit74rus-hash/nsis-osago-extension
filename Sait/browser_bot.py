import os
import time
import pytesseract
from playwright.sync_api import sync_playwright
from PIL import Image
from config import TESSERACT_PATH
from image_processor import preprocess_captcha

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

def check_osago_via_nsis(search_type, query_value):
    with sync_playwright() as p:
        print("🤖 Запускаю встроенный браузер с обходом защитных блокировок...")
        launch_args = ["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-setuid-sandbox"]
        
        try:
            browser = p.chromium.launch(headless=True, channel="chrome", args=launch_args)
        except Exception:
            try:
                browser = p.chromium.launch(headless=True, channel="msedge", args=launch_args)
            except Exception as e:
                return f"❌ Ошибка запуска локального браузера: {e}"

        context = browser.new_context(
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print("🤖 Перехожу на сайт НСИС...")
        try:
            page.goto("https://nsis.ru", timeout=60000, wait_until="networkidle")
            page.wait_for_timeout(3000) 
        except Exception as e:
            browser.close()
            return f"❌ Сайт НСИС не ответил вовремя. ({e})"

        captcha_text = ""
        for attempt in range(1, 5):
            print(f"🔍 Ищу капчу на странице (Попытка {attempt})...")
            captcha_selector = 'img[src*="captcha"], .captcha-image img, img[alt*="Капча"], div[class*="captcha"] img'
            
            try:
                page.wait_for_selector(captcha_selector, timeout=10000)
                captcha_element = page.query_selector(captcha_selector)
            except Exception:
                captcha_element = None

            if not captcha_element:
                browser.close()
                return "❌ Не удалось найти капчу на странице сайта."

            captcha_path = "captcha_temp.png"
            captcha_element.screenshot(path=captcha_path)
            processed_path = preprocess_captcha(captcha_path)

            try:
                img = Image.open(processed_path)
                custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789'
                raw_text = pytesseract.image_to_string(img, config=custom_config).strip()
                img.close()
                if os.path.exists(captcha_path): os.remove(captcha_path)
                if os.path.exists(processed_path) and processed_path != captcha_path: os.remove(processed_path)
                
                # Очищаем текст от случайных пробелов
                captcha_text = raw_text.replace(" ", "").strip()
            except Exception as e:
                browser.close()
                return f"❌ Ошибка Tesseract: {e}"

            # Умный срез: если Tesseract нашел лишние символы по краям, берем первые 6 цифр
            if len(captcha_text) >= 6:
                captcha_text = captcha_text[:6]
                print(f"✅ Капча успешно адаптирована под формат НСИС: {captcha_text}")
                break
            else:
                print(f"⚠️ Текст капчи слишком короткий ({captcha_text}), перезапрашиваю картинку...")
                if captcha_element:
                    captcha_element.click()
                    page.wait_for_timeout(2000)
                captcha_text = ""

        if not captcha_text or len(captcha_text) != 6:
            browser.close()
            return f"❌ Робот не смог точно распознать капчу (результат: {captcha_text}). Попробуйте еще раз."

        try:
            # Заполняем поля формы
            if search_type == "vin": page.fill('input[name="vin"]', query_value)
            elif search_type == "reg": page.fill('input[name="regNum"]', query_value)
            elif search_type == "body": page.fill('input[name="bodyNum"]', query_value)
            
            page.fill('input[name="captcha"]', captcha_text)
            
            # ВАЖНАЯ ПАУЗА: Даем сайту 1 секунду «переварить» ввод данных, чтобы они закрепились в форме
            page.wait_for_timeout(1000)
            
            submit_btn = page.query_selector('button[type="submit"]')
            if submit_btn: submit_btn.click()
        except Exception as e:
            browser.close()
            return f"❌ Ошибка заполнения полей формы: {e}"

        print("⏱ Ожидаю ответ от базы данных...")
        for _ in range(60):
            time.sleep(0.5)
            site_text = page.evaluate("() => document.body.innerText")
            
            if "Неверный код" in site_text or "Капча введена неверно" in site_text:
                browser.close()
                return f"❌ Ошибка капчи: Сайт отклонил код ({captcha_text}). Попробуйте еще раз!"
            
            if "Поле заполнено некорректно" in site_text or "неверный формат" in site_text.lower():
                browser.close()
                return "❌ Ошибка: Сайт сообщил, что VIN или Госномер заполнены в неверном формате."
            
            if "Серия полиса" in site_text or "Номер полиса" in site_text or "Статус договора" in site_text:
                main_element = page.query_selector('main')
                main_text = main_element.inner_text() if main_element else site_text
                browser.close()
                return main_text
                
            if "не найден" in site_text or "Полис отсутствует" in site_text or "Ничего не найдено" in site_text:
                browser.close()
                return "⚠️ Полис ОСАГО с такими данными не найден в базе НСИС."

        browser.close()
        return "⏱ Время ожидания ответа базы изменилось или истекло. Проверьте правильность VIN-кода."
