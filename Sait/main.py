from flask import Flask, render_template_string, request, jsonify
from browser_bot import check_osago_via_nsis

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>NSIS Premium Web Panel</title>
    <meta charset="utf-8">
    <style>
        body { font-family: system-ui, sans-serif; background: #f4f6f9; padding: 40px; display: flex; justify-content: center; }
        .panel { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); width: 450px; }
        h2 { margin-top: 0; color: #1e293b; text-align: center; }
        .form-group { margin-bottom: 15px; }
        label { display: block; font-size: 12px; color: #64748b; margin-bottom: 5px; text-transform: uppercase; }
        select, input, button { width: 100%; padding: 12px; box-sizing: border-box; border-radius: 6px; border: 1px solid #cbd5e1; font-size: 14px; }
        button { background: #2563eb; color: white; border: none; font-weight: bold; cursor: pointer; margin-top: 10px; }
        button:hover { background: #1d4ed8; }
        #loader { text-align: center; color: #64748b; margin-top: 15px; font-size: 14px; }
        #result { margin-top: 20px; white-space: pre-wrap; background: #f8fafc; padding: 15px; border-radius: 6px; border: 1px solid #e2e8f0; font-size: 13px; color: #334155; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="panel">
        <h2>NSIS Premium Bot</h2>
        <form id="searchForm">
            <div class="form-group">
                <label>Тип поиска</label>
                <select id="searchType">
                    <option value="vin">VIN-код</option>
                    <option value="reg">Госномер</option>
                    <option value="body">Номер кузова</option>
                </select>
            </div>
            <div class="form-group">
                <label>Значение</label>
                <input type="text" id="queryValue" placeholder="Введите данные..." required>
            </div>
            <button type="submit">Запустить проверку</button>
        </form>
        <div id="loader" class="hidden">🤖 Робот открывает НСИС, улучшает контраст и разгадывает капчу... Пожалуйста, подождите.</div>
        <div id="result" class="hidden"></div>
    </div>

    <script>
        document.getElementById('searchForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const loader = document.getElementById('loader');
            const resultDiv = document.getElementById('result');
            
            loader.classList.remove('hidden');
            resultDiv.classList.add('hidden');
            
            const response = await fetch('/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    type: document.getElementById('searchType').value,
                    value: document.getElementById('queryValue').value
                })
            });
            const data = await response.json();
            
            loader.classList.add('hidden');
            resultDiv.innerText = data.result;
            resultDiv.classList.remove('hidden');
        });
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/search', methods=['POST'])
def search():
    data = request.get_json()
    search_type = data.get('type')
    query_value = data.get('value')
    
    output = check_osago_via_nsis(search_type, query_value)
    return jsonify({'result': output})

if __name__ == '__main__':
    print("🚀 Локальная веб-панель запускается...")
    print("👉 ОТКРОЙТЕ В БРАУЗЕРЕ ССЫЛКУ: http://127.0.0.1:5000")
    app.run(debug=False, port=5000)
