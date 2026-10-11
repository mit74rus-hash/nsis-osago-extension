from flask import Flask, render_template, request, jsonify
from bot.agent_core import process_chat_message

app = Flask(__name__)

# Храним историю чата в памяти (для локального использования этого достаточно)
chat_history = [
    {
        "role": "system", 
        "content": "Ты — умный ассистент по проверке страхования ОСАГО в России. "
                   "Используй инструмент check_osago_policy для поиска данных. "
                   "Отвечай кратко, вежливо и по делу. Форматируй ответ так, чтобы его было легко читать."
    }
]

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({"error": "Пустое сообщение"}), 400

    result = process_chat_message(user_message, chat_history)
    return jsonify(result)

@app.route('/api/clear', methods=['POST'])
def clear_chat():
    global chat_history
    chat_history = [chat_history[0]] # Оставляем только системный промпт
    return jsonify({"status": "cleared"})

if __name__ == '__main__':
    print("🚀 Запуск веб-панели с AI-агентом...")
    print("👉 ОТКРОЙТЕ В БРАУЗЕРЕ: http://127.0.0.1:5000")
    app.run(debug=False, port=5000)