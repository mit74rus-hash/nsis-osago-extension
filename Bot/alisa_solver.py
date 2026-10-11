import re
import time

ALISA_URL = "https://alice.yandex.ru/"

class AlisaSolver:
    """Решает капчу через чат с Алисой в отдельной вкладке"""

    def __init__(self, context):
        self.context = context
        self.page = None
        self.ready = False

    def _find_input_box(self):
        for sel in ('textarea', 'input[type="text"]', '[contenteditable="true"]'):
            try:
                el = self.page.query_selector(sel)
                if el and el.is_visible():
                    return el
            except Exception:
                continue
        return None

    def open(self):
        try:
            self.page = self.context.new_page()
            self.page.goto(ALISA_URL, timeout=60000, wait_until="domcontentloaded")
            self.page.wait_for_timeout(3000)

            for _ in range(6):
                if self._find_input_box() is not None:
                    self.ready = True
                    print("🧠 Алиса готова решать капчи")
                    return True
                self.page.wait_for_timeout(2000)

            print("🔐 Нужен вход: залогинься в Яндекс во вкладке с Алисой (открыта в браузере).")
            input("   Когда увидишь чат с полем ввода — нажми Enter здесь в консоли...")
            for _ in range(15):
                if self._find_input_box() is not None:
                    self.ready = True
                    print("🧠 Алиса готова решать капчи")
                    return True
                self.page.wait_for_timeout(2000)

            print("⚠️ Чат Алисы не дождался. Капчу буду решать другими способами.")
            return False
        except Exception as e:
            print(f"⚠️ Не удалось открыть Алису: {e}")
            return False

    def solve(self, image_path, exclude=None, timeout=45):
        """Прикрепляет картинку, спрашивает цифры, возвращает код или None"""
        if not self.ready:
            return None
        exclude = exclude or set()
        try:
            before = self.page.evaluate("() => document.body.innerText")

            # Сначала кликаем по кнопке прикрепления (скрепка), потом ищем input[type=file]
            for sel in ('button[title*="рикрепить"]', '[aria-label*="рикрепить"]',
                        'button[title*="файл"]', '[aria-label*="файл"]',
                        'button[data-test-id*="attach"]'):
                btn = self.page.query_selector(sel)
                if btn:
                    btn.click()
                    self.page.wait_for_timeout(1500)
                    break

            file_input = self.page.query_selector('input[type="file"]')
            if not file_input:
                print("⚠️ Алиса: не найдена кнопка прикрепления файла")
                return None
            file_input.set_input_files(image_path)
            self.page.wait_for_timeout(2500)

            box = self._find_input_box()
            if not box:
                return None
            box.click()
            box.fill("Какие цифры на картинке? Ответь только цифрами, без пробелов и слов.")
            self.page.keyboard.press("Enter")

            deadline = time.time() + timeout
            while time.time() < deadline:
                self.page.wait_for_timeout(1500)
                after = self.page.evaluate("() => document.body.innerText")
                delta = after[len(before):] if after.startswith(before) else after[-3000:]
                matches = [c for c in re.findall(r'\b(\d{6,7})\b', delta) if c not in exclude]
                if matches:
                    print(f"🧠 Алиса прочитала капчу: {matches[0]}")
                    return matches[0]
            print("⚠️ Алиса не вернула цифры вовремя")
            return None
        except Exception as e:
            print(f"⚠️ Ошибка Алисы: {e}")
            return None