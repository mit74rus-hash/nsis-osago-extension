function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, s =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[s])
  );
}

function getCompanyInitials(companyName) {
  if (!companyName) return 'СК';
  const words = companyName.trim().split(/\s+/);
  if (words.length === 0 || !words[0]) return 'СК';
  return words[0].substring(0, 2).toUpperCase();
}

function showResult(message, type, showRetry = false) {
  const resultDiv = document.getElementById('result');
  if (!resultDiv) return;
  let retryButton = '';
  if (showRetry) {
    retryButton = `<button onclick="retryLastSearch()" style="margin-top: 10px; width: 100%; padding: 10px; background-color: #2563eb; color: white; border: none; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer;">🔄 Повторить запрос</button>`;
  }
  resultDiv.innerHTML = `<div class="card ${type}">${message}${retryButton}</div>`;
  resultDiv.classList.remove('hidden');
}

function renderPremiumCard(fullText) {
  const resultDiv = document.getElementById('result');
  if (!resultDiv) return;
  
  // Разрезаем большой текст ответа сайта на отдельные блоки по началу каждого полиса
  const policyBlocks = fullText.split(/(?=Серия полиса[:\s]*)/i).filter(block => block.toLowerCase().includes('серия полиса'));
  
  if (policyBlocks.length === 0) {
    showResult("⚠️ Не удалось разобрать структуру ответа НСИС.", "warning");
    return;
  }

  const INSURANCE_LOGOS = {
    'согаз': 'https://wikimedia.org',
    'ингосстрах': 'https://wikimedia.org',
    'росгосстрах': 'https://wikimedia.org',
    'альфастрахование': 'https://wikimedia.org',
    'ресо': 'https://wikimedia.org',
    'вск': 'https://wikimedia.org'
  };

  let finalHTML = '';

  // Перебираем каждый найденный полис и генерируем для него собственную карточку
  policyBlocks.forEach(block => {
    const seriesMatch = block.match(/Серия полиса[:\s]*([A-Za-zА-Яа-я0-9-]+)/i);
    const numberMatch = block.match(/Номер полиса[:\s]*([0-9]+)/i);
    const statusMatch = block.match(/Статус договора(?:\s+ОСАГО)?[:\s]*([^\n\(\r\)]+)/i);
    const modelMatch = block.match(/Марка\s+(?:и\s+модель)?\s+ТС[:\s]*([^\n\(\r\)]+)/i);
    const companyMatch = block.match(/Страховая\s+компания[:\s]*([^\n\(\r\)]+)/i);
    const dateStartMatch = block.match(/(?:Начало\s+действия|Окончание\s+действия[^]*?Начало\s+действия|действия\s+договора)[:\s]*(\d{2}[.\-/]\d{2}[.\-/]\d{4})/i);

    const series = seriesMatch ? seriesMatch[1] : "ХХХ";
    const number = numberMatch ? numberMatch[1] : "Не найден";
    const status = statusMatch ? statusMatch[1].trim() : "Неизвестен";
    const model = modelMatch ? modelMatch[1].trim() : "Автомобиль";
    const company = companyMatch ? companyMatch[1].trim() : "Страховая компания";
    
    // Продвинутый поиск даты начала действия (если регулярка выше не зацепила)
    let dateStart = "Не указано";
    if (dateStartMatch) {
      dateStart = dateStartMatch[1];
    } else {
      const backupDate = block.match(/(\d{2}[.\-/]\d{2}[.\-/]\d{4})/);
      if (backupDate) dateStart = backupDate[1];
    }
    
    const companyLower = company.toLowerCase();
    let logoUrl = null;
    for (const [key, url] of Object.entries(INSURANCE_LOGOS)) {
      if (companyLower.includes(key)) {
        logoUrl = url;
        break;
      }
    }
    
    let logoHTML = '';
    if (logoUrl) {
      logoHTML = `<img class="company-logo" src="${logoUrl}" alt="Логотип">`;
    } else {
      const initials = getCompanyInitials(company);
      logoHTML = `<div class="company-logo" style="background-color: #2563eb; color: white; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 11px; width: 28px; height: 28px; border-radius: 4px;">${escapeHtml(initials)}</div>`;
    }

    // Подбираем цвет индикатора в зависимости от статуса полиса
    let statusClass = 'active';
    if (status.toLowerCase().includes('не начался')) {
      statusClass = 'pending'; // Желтый или серый цвет для будущих полисов
    } else if (status.toLowerCase().includes('прекращен') || status.toLowerCase().includes('истек')) {
      statusClass = 'expired'; // Красный цвет
    }
    
    finalHTML += `
      <div class="premium-card" style="margin-bottom: 12px;">
        <div class="premium-header">
          ${logoHTML}
          <div class="company-name">${escapeHtml(company.replace(/["'«»]/g, ''))}</div>
        </div>
        <div class="policy-main-info">
          <span class="policy-badge">ОСАГО</span>
          <span class="policy-number">${escapeHtml(series)} № ${escapeHtml(number)}</span>
        </div>
        <div class="status-row">
          <span class="status-indicator ${statusClass}"></span>
          <span class="status-text">Договор: <b>${escapeHtml(status)}</b></span>
        </div>
        <div class="info-grid">
          <div class="info-item"><span>Автомобиль:</span> <b>${escapeHtml(model)}</b></div>
          <div class="info-item"><span>Начало действия:</span> <b>${escapeHtml(dateStart)}</b></div>
        </div>
      </div>
    `;
  });

  resultDiv.innerHTML = finalHTML;
  resultDiv.classList.remove('hidden');
}
