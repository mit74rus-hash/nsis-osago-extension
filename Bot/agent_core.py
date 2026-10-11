import os
import re
import json
import urllib.request
from openai import OpenAI
from .browser_bot import check_osago_via_nsis

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_osago_policy",
            "description": "Проверяет факт страхования ОСАГО в базе НСИС. Используй, когда просят проверить страховку/полис по VIN, госномеру или номеру кузова.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_type": {"type": "string", "enum": ["vin", "reg", "body"], "description": "vin, reg или body"},
                    "query_value": {"type": "string", "description": "Значение для поиска"}
                },
                "required": ["search_type", "query_value"]
            }
        }
    }
]

TOOL_IMPL = {"check_osago_policy": check_osago_via_nsis}

def clean_think(text):
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()

def process_chat_message(user_message, history):
    """Обрабатывает сообщение и возвращает ответ + статус инструментов"""
    history.append({"role": "user", "content": user_message})
    
    # Ограничиваем историю, чтобы не переполнять память
    messages = [history[0]] + history[1:][-10:]

    tool_status = None

    while True:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.1,
        )
        msg = resp.choices[0].message

        if not msg.tool_calls:
            # Финальный ответ от ИИ
            answer = clean_think(msg.content)
            history.append({"role": "assistant", "content": answer})
            return {"response": answer, "tool_status": tool_status}

        # ИИ хочет использовать инструмент
        history.append(msg)
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}
            
            tool_status = {"name": name, "args": args, "status": "running"}
            
            fn = TOOL_IMPL.get(name)
            if fn:
                try:
                    result = fn(**args)
                    tool_status["result"] = result
                except Exception as e:
                    tool_status["result"] = f"Ошибка: {e}"
            else:
                tool_status["result"] = "Неизвестный инструмент"

            history.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": str(tool_status["result"])[:3000],
            })