const CHECK_URL_PATTERN = "*://*.nsis.ru/products/osago/check/*";

function safeAddListener(id, event, handler) {
  const el = document.getElementById(id);
  if (el) {
    el.addEventListener(event, handler);
  } else {
    console.warn(`Элемент #${id} не найден`);
  }
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, s =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[s])
  );
}

function getCompanyInitials(companyName) {
  const words = companyName.trim().split(/\s+/);
  if (words.length === 0) return 'СК';
  return words[0].substring(0, 2).toUpperCase();
}

document.addEventListener('DOMContentLoaded', initExtension);
safeAddListener('refreshCaptchaBtn', 'click', triggerSiteCaptchaRefresh);
safeAddListener('recognizeCaptchaBtn', 'click', async () => {
  const captchaInput = document.getElementById('captchaInput');
  const loader = document.getElementById('loader');
  if (loader) loader.classList.remove('hidden');
  const recognized = await recognizeCaptcha();
  if (loader) loader.classList.add('hidden');
  if (recognized && captchaInput) {
    captchaInput.value = recognized;
    showResult(`✅ Капча распознана: <b>${recognized}</b>`, "success");
  } else {
    showResult("❌ Не удалось распознать. Введите вручную.", "error");
  }
});
safeAddListener('searchBtn', 'click', handleSearch);

async function initExtension() {
  try {
    const captchaImg = document.getElementById('captchaImg');
    const resultDiv = document.getElementById('result');
    if (!captchaImg) return;

    captchaImg.alt = "Ищем вкладку...";
    const tabs = await chrome.tabs.query({ url: CHECK_URL_PATTERN });
    
    if (!tabs || tabs.length === 0) {
      captchaImg.alt = "Вкладка закрыта";
      showResult("⚠️ Пожалуйста, откройте страницу проверки в соседней вкладке:<br><a href='https://nsis.ru/products/osago/check/' target='_blank'>nsis.ru/products/osago/check/</a>", "warning");
      return;
    }
    
    const tab = tabs[0];
    captchaImg.alt = "Считываем код...";
    
    chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        const img = document.querySelector('img[src*="captcha"], .captcha-image img, div[class*="captcha"] img');
        return img ? img.src : null;
      }
    }, (results) => {
      if (chrome.runtime.lastError) {
        console.error(chrome.runtime.lastError);
        captchaImg.alt = "Ошибка доступа";
        return;
      }
      if (results && results[0] && results[0].result) {
        captchaImg.src = results[0].result;
        if (resultDiv) resultDiv.classList.add('hidden');
      } else {
        captchaImg.alt = "Не найдено";
      }
    });
  } catch (error) {
    console.error('Ошибка в initExtension:', error);
  }
}

async function triggerSiteCaptchaRefresh() {
  try {
    const tabs = await chrome.tabs.query({ url: CHECK_URL_PATTERN });
    if (!tabs || tabs.length === 0) return;
    
    chrome.scripting.executeScript({
      target: { tabId: tabs[0].id },
      func: () => {
        const refreshBtn = Array.from(document.querySelectorAll('button, span, a'))
          .find(el => el.innerText.includes('Обновить') || el.className.includes('refresh'));
        if (refreshBtn) {
          refreshBtn.click();
        } else {
          location.reload();
        }
      }
    });
    setTimeout(initExtension, 1200);
  } catch (error) {
    console.error('Ошибка при обновлении капчи:', error);
  }
}

async function recognizeCaptcha() {
  try {
    const captchaImg = document.getElementById('captchaImg');
    if (!captchaImg || !captchaImg.src) return null;
    
    const result = await Tesseract.recognize(captchaImg.src, 'rus', {
      logger: m => console.log(m)
    });
    
    const recognized = result.data.text.replace(/[^A-Za-zА-Яа-я0-9]/g, '').trim();
    console.log('Распознанная капча:', recognized);
    return recognized || null;
  } catch (error) {
    console.error('Ошибка распознавания капчи:', error);
    return null;
  }
}

async function handleSearch() {
  try {
    const searchType = document.getElementById('searchType').value;
    const queryInput = document.getElementById('queryInput');
    const captchaInput = document.getElementById('captchaInput');
    const resultDiv = document.getElementById('result');
    const loader = document.getElementById('loader');
    
    if (!queryInput || !captchaInput) return;
    
    const queryValue = queryInput.value.trim();
    let captchaWord = captchaInput.value.trim();
    
    if (!queryValue) {
      showResult("⚠️ Заполните поисковое поле!", "error");
      return;
    }
    
    if (!captchaWord) {
      if (loader) loader.classList.remove('hidden');
      showResult("🔍 Распознаю капчу...", "info");
      captchaWord = await recognizeCaptcha();
      if (!captchaWord) {
        if (loader) loader.classList.add('hidden');
        showResult("❌ Не удалось распознать капчу. Введите вручную.", "error");
        return;
      }
      captchaInput.value = captchaWord;
      showResult(`✅ Капча распознана: <b>${captchaWord}</b>`, "success");
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
    
    if (resultDiv) resultDiv.classList.add('hidden');
    if (loader) loader.classList.remove('hidden');
    
    const tabs = await chrome.tabs.query({ url: CHECK_URL_PATTERN });
    if (!tabs || tabs.length === 0) {
      if (loader) loader.classList.add('hidden');
      showResult("❌ Вкладка НСИС была закрыта.", "error");
      return;
    }
    
    const tab = tabs[0];
    
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        location.reload();
      }
    });
    
    let captchaUrl = null;
    let attempts = 0;
    const maxAttempts = 10;
    
    while (!captchaUrl && attempts < maxAttempts) {
      await new Promise(resolve => setTimeout(resolve, 500));
      captchaUrl = await new Promise((resolve) => {
        chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: () => {
            const img = document.querySelector('img[src*="captcha"]') || 
                       document.querySelector('.captcha-image img') || 
                       document.querySelector('img[alt*="Капча"]');
            return img && img.src && !img.src.includes('data:image/svg+xml') ? img.src : null;
          }
        }, (results) => {
          if (chrome.runtime.lastError) {
            resolve(null);
          } else if (results && results[0] && results[0].result) {
            resolve(results[0].result);
          } else {
            resolve(null);
          }
        });
      });
      attempts++;
    }
    
    if (captchaUrl) {
      const captchaImg = document.getElementById('captchaImg');
      if (captchaImg) {
        captchaImg.src = captchaUrl;
        captchaImg.alt = "Капча загружена";
      }
    } else {
      if (loader) loader.classList.add('hidden');
      showResult("⚠️ Не удалось загрузить капчу. Попробуйте ещё раз.", "warning", true);
      return;
    }
    
    chrome.scripting.executeScript({
      target: { tabId: tab.id },
      args: [searchType, queryValue, captchaWord],
      func: (type, value, captcha) => {
        const inputs = Array.from(document.querySelectorAll('input[type="text"], input:not([type])'));
        if (inputs.length < 6) return;
        
        const changeInputValue = (input, val) => {
          const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
          nativeInputValueSetter.call(input, val);
          input.dispatchEvent(new Event('input', { bubbles: true }));
          input.dispatchEvent(new Event('change', { bubbles: true }));
        };
        
        for (let i = 0; i < 4; i++) {
          if (inputs[i]) changeInputValue(inputs[i], '');
        }
        
        if (type === 'regNumber' && inputs[0]) changeInputValue(inputs[0], value);
        if (type === 'vin' && inputs[1]) changeInputValue(inputs[1], value);
        if (type === 'bodyNumber' && inputs[2]) changeInputValue(inputs[2], value);
        
        if (inputs[5]) changeInputValue(inputs[5], captcha);
        
        const submitBtn = Array.from(document.querySelectorAll('button'))
          .find(b => b.innerText.includes('Отправить') || b.innerText.includes('Проверить'));
        if (submitBtn) submitBtn.click();
      }
    }, () => {
      if (chrome.runtime.lastError) {
        console.error(chrome.runtime.lastError);
        if (loader) loader.classList.add('hidden');
        showResult("❌ Ошибка выполнения скрипта", "error");
        return;
      }
      waitForResult(tab.id, loader);
    });
  } catch (error) {
    console.error('Ошибка в handleSearch:', error);
    showResult("⚠️ Ошибка: " + error.message, "error");
  }
}

function waitForResult(tabId, loader, attempts = 0) {
  const maxAttempts = 30;
  const delay = 500;
  
  if (attempts >= maxAttempts) {
    if (loader) loader.classList.add('hidden');
    showResult("⏱ Время ожидания истекло. Попробуйте ещё раз или посмотрите вкладку НСИС.", "warning", true);
    return;
  }
  
  setTimeout(() => {
    chrome.scripting.executeScript({
      target: { tabId: tabId },
      func: () => {
        const bodyText = document.body.innerText;
        const modal = document.querySelector('[class*="modal"], [class*="dialog"], [role="dialog"]');
        const modalText = modal ? modal.innerText : '';
        
        if (modalText.includes("попробуйте еще раз") || 
            modalText.includes("попробуйте ещё раз") ||
            bodyText.includes("попробуйте еще раз") ||
            bodyText.includes("попробуйте ещё раз")) {
          return { status: "server_error", message: "Сервер НСИС перегружен" };
        }
        if (modalText.includes("пике активности") || 
            bodyText.includes("пике активности")) {
          return { status: "server_busy", message: "Сервер на пике активности" };
        }
        if (modalText.includes("Сервис временно недоступен") ||
            bodyText.includes("Сервис временно недоступен")) {
          return { status: "server_unavailable", message: "Сервис временно недоступен" };
        }
        if (modalText.includes("Ошибка сервера") ||
            bodyText.includes("Ошибка сервера") ||
            bodyText.includes("500") ||
            bodyText.includes("502") ||
            bodyText.includes("503")) {
          return { status: "server_error", message: "Ошибка сервера НСИС" };
        }
        if (bodyText.includes("Неверный код") || 
            bodyText.includes("Капча введена неверно") ||
            bodyText.includes("неверно") ||
            modalText.includes("неверно")) {
          return { status: "captcha_error" };
        }
        if (bodyText.includes("Данные о полисах ОСАГО") || 
            bodyText.includes("Статус договора") ||
            bodyText.includes("Серия полиса") ||
            bodyText.includes("Номер полиса")) {
          return { status: "success", text: document.body.innerText };
        }
        if (bodyText.includes("не найден") || 
            bodyText.includes("Полис отсутствует") ||
            bodyText.includes("Ничего не найдено") ||
            bodyText.includes("Полис не найден")) {
          return { status: "not_found" };
        }
        if (modal && modalText && 
            (modalText.includes("Ошибка") || 
             modalText.includes("ошибка") ||
             modalText.includes("Не удалось") ||
             modalText.includes("Превышено"))) {
          return { status: "modal_error", message: modalText.substring(0, 100) };
        }
        return { status: "waiting" };
      }
    }, (results) => {
      if (chrome.runtime.lastError) {
        if (loader) loader.classList.add('hidden');
        return;
      }
      if (results && results[0] && results[0].result) {
        const res = results[0].result;
        switch (res.status) {
          case "captcha_error":
            if (loader) loader.classList.add('hidden');
            showResult("❌ Неверный код капчи! Введите обновлённый код.", "error");
            initExtension();
            break;
          case "server_error":
          case "server_busy":
          case "server_unavailable":
            if (loader) loader.classList.add('hidden');
            showResult(`️ ${res.message || 'Ошибка сервера НСИС'}. Нажмите кнопку ниже, чтобы повторить запрос.`, "warning", true);
            break;
          case "modal_error":
            if (loader) loader.classList.add('hidden');
            showResult(`️ Ошибка: ${res.message}. Попробуйте ещё раз.`, "warning", true);
            break;
          case "success":
            if (loader) loader.classList.add('hidden');
            renderPremiumCard(res.text);
            break;
          case "not_found":
            if (loader) loader.classList.add('hidden');
            showResult("⚠️ Страховка ОСАГО не найдена в базе.", "warning");
            initExtension();
            break;
          default:
            waitForResult(tabId, loader, attempts + 1);
        }
      }
    });
  }, delay);
}

function renderPremiumCard(fullText) {
  const resultDiv = document.getElementById('result');
  if (!resultDiv) return;
  
  const series = (fullText.match(/Серия полиса[:\s]*([A-Za-zА-Яа-я0-9-]+)/i) || ["", "ХХХ"])[1];
  const number = (fullText.match(/Номер полиса[:\s]*([0-9]+)/i) || ["", "Не найден"])[1];
  const status = (fullText.match(/Статус договора(?:\s+ОСАГО)?[:\s]*([^\n\r]+)/i) || ["", "Неизвестен"])[1].trim();
  const model = (fullText.match(/Марка\s+(?:и\s+модель)?\s+ТС[:\s]*([^\n\r]+)/i) || ["", "Автомобиль"])[1].trim();
  const company = (fullText.match(/Страховая\s+компания[:\s]*([^\n\r]+)/i) || ["", "Страховая компания"])[1].trim();
  const dateStart = (fullText.match(/Начало\s+действия\s+(?:договора)?[:\s]*(\d{2}[.\-/]\d{2}[.\-/]\d{4})/i) || 
                     fullText.match(/Начало\s+действия[:\s]*([^\n\r\d]*\d{2}[.\-/]\d{2}[.\-/]\d{4}[^\n\r]*)/i) || 
                     ["", "Не указано"])[1].trim();
  
  const INSURANCE_LOGOS = {
    'согаз': 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/0e/Sogaz_logo.svg/200px-Sogaz_logo.svg.png',
    'ингосстрах': 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/8f/Ingosstrakh_logo.svg/200px-Ingosstrakh_logo.svg.png',
    'росгосстрах': 'https://upload.wikimedia.org/wikipedia/commons/thumb/3/3e/Rosgosstrakh_logo.svg/200px-Rosgosstrakh_logo.svg.png',
    'альфастрахование': 'https://upload.wikimedia.org/wikipedia/commons/thumb/9/9a/AlfaStrakhovanie_logo.svg/200px-AlfaStrakhovanie_logo.svg.png',
    'тинькофф': 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Tinkoff_Bank_logo.svg/200px-Tinkoff_Bank_logo.svg.png',
    'т-страхование': 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Tinkoff_Bank_logo.svg/200px-Tinkoff_Bank_logo.svg.png',
    'ресо': 'https://upload.wikimedia.org/wikipedia/commons/thumb/7/7e/RESO-Garant_logo.svg/200px-RESO-Garant_logo.svg.png',
    'вск': 'https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/VSK_logo.svg/200px-VSK_logo.svg.png',
    'согласие': 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/6e/Soglasie_logo.svg/200px-Soglasie_logo.svg.png',
    'югория': 'https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Yugoria_logo.svg/200px-Yugoria_logo.svg.png',
    'макс': 'https://upload.wikimedia.org/wikipedia/commons/thumb/2/2e/MAX_logo.svg/200px-MAX_logo.svg.png',
    'аско': 'https://upload.wikimedia.org/wikipedia/commons/thumb/1/1e/ASKO_logo.svg/200px-ASKO_logo.svg.png'
  };
  
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
    logoHTML = `<img class="company-logo" src="${logoUrl}" alt="Логотип" style="width: 32px; height: 32px; object-fit: contain;">`;
  } else {
    const initials = getCompanyInitials(company);
    const colors = ['#2563eb', '#dc2626', '#16a34a', '#9333ea', '#ea580c'];
    const bgColor = colors[company.length % colors.length];
    logoHTML = `<div class="company-logo" style="background-color: ${bgColor}; color: white; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 11px; width: 28px; height: 28px; border-radius: 4px; flex-shrink: 0;">${escapeHtml(initials)}</div>`;
  }
  
  resultDiv.innerHTML = `
    <div class="premium-card">
      <div class="premium-header">
        ${logoHTML}
        <div class="company-name" style="word-break: break-word; line-height: 1.3;">${escapeHtml(company.replace(/["'«»]/g, ''))}</div>
      </div>
      <div class="policy-main-info">
        <span class="policy-badge">ОСАГО</span>
        <span class="policy-number">${escapeHtml(series)} № ${escapeHtml(number)}</span>
      </div>
      <div class="status-row">
        <span class="status-indicator active"></span>
        <span class="status-text">Договор: <b>${escapeHtml(status)}</b></span>
      </div>
      <div class="info-grid">
        <div class="info-item"><span>Автомобиль:</span> <b>${escapeHtml(model)}</b></div>
        <div class="info-item"><span>Начало действия:</span> <b>${escapeHtml(dateStart)}</b></div>
      </div>
    </div>
  `;
  resultDiv.classList.remove('hidden');
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

window.retryLastSearch = function() {
  const loader = document.getElementById('loader');
  const resultDiv = document.getElementById('result');
  if (resultDiv) resultDiv.classList.add('hidden');
  if (loader) loader.classList.remove('hidden');
  triggerSiteCaptchaRefresh();
  setTimeout(() => {
    handleSearch();
  }, 1500);
};