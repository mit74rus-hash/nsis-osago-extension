import os
import re
import json
import urllib.request
from openai import OpenAI
from browser_bot import check_osago_via_nsis

# ===== OLLAMA (ЛОКАЛЬНО, БЕЗ ИНТЕРНЕТА ДЛЯ РАБОТЫ) =====
client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")  # ключ-заглушка, Ollama он не нужен
MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")   # можно: llama3.1:8b, qwen3:4b

# ===== ОПИСАНИЕ ИНСТРУМЕНТОВ =====
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_osago_policy",
            "description": "Проверяет факт страхования ОСАГО в базе НСИС. "
                           "Используй, когда просят проверить страховку/полис ОСАГО "
                           "по VIN, госномеру или номеру кузова.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_type": {
                        "type": "string",
                        "enum": ["vin", "reg", "body"],
                        "description": "vin = VIN-код (17 символов), reg = госномер, body = номер кузова"
                    },
                    "query_value": {
                        "type": "string",
                        "description": "Значение для поиска"
                    }
                },
                "required": ["search_type", "query_value"]
            }
        }
    }
]

TOOL_IMPL = {
    "check_osago_policy": check_osago_via_nsis
}

def ensure_ollama():
    """Проверяет, что Ollama запущен и модель скачана"""
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5) as r:
            data = json.load(r)
        names = [m["name"] for m in data.get("models", [])]
        if not any(n == MODEL or n.startswith(MODEL.split(":")[0] + ":") for n in names):
            print(f"⚠️ Модель '{MODEL}' не найдена. Скачай её командой:  ollama pull {MODEL}")
            return False
        return True
    except Exception:
        print("⚠️ Ollama не запущен! Запусти приложение Ollama или команду:  ollama serve")
        return False

def clean_think(text):
    """Убирает служебные размышления Qwen3 <think>...</think> из ответа"""
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()

def trim_history(history, max_msgs=12):
    """Держим контекст коротким, чтобы влезать в память локальной модели"""
    return [history[0]] + history[1:][-max_msgs:]

def chat_loop():
    history = [
        {"role": "system", "content": (
            "Ты — ассистент по проверке страхования ОСАГО в России. "
            "Для поиска информации о полисах используй инструмент check_osago_policy. "
            "Отвечай кратко, по-русски, без лишних размышлений. "
            "Если полис не найден или проверка не удалась — скажи об этом честно."
        )}
    ]

    print(f" Локальный агент на модели {MODEL} готов.")
    print("   Примеры задач:")
    print("   • «Проверь ОСАГО по VIN WF0MXXGBWM8A69085»")
    print("   • «Есть ли страховка у машины с госномером К891ОI74?»")
    print("   • exit — выход")
    print()

    while True:
        user_msg = input("Вы: ").strip()
        if not user_msg or user_msg.lower() in ("exit", "quit", "выход"):
            break

        history.append({"role": "user", "content": user_msg})

        # Цикл: модель может вызвать инструмент несколько раз подряд
        while True:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=trim_history(history),
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.1,   # поменьше фантазий, побольше точности
            )
            msg = resp.choices[0].message

            # Модель ответила текстом — показываем и выходим из цикла
            if not msg.tool_calls:
                answer = clean_think(msg.content)
                print(f"\n🤖 Агент: {answer}\n")
                history.append({"role": "assistant", "content": answer})
                break

            # Модель просит инструмент
            history.append(msg)
            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except Exception:
                    args = {}
                print(f"   🔧 Агент вызывает: {name}({args})")

                fn = TOOL_IMPL.get(name)
                if fn:
                    try:
                        result = fn(**args)
                    except Exception as e:
                        result = f"Ошибка инструмента: {e}"
                else:
                    result = f"Неизвестный инструмент: {name}"

                history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(result)[:3000],
                })

if __name__ == "__main__":
    if ensure_ollama():
        chat_loop()