const CHECK_URL_PATTERN = "*://*.nsis.ru/products/osago/check/*";

function safeAddListener(id, event, handler) {
  const el = document.getElementById(id);
  if (el) el.addEventListener(event, handler);
  else console.warn(`Элемент #${id} не найден`);
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
      showResult("⚠️ Пожалуйста, откройте страницу проверки в соседней вкладке:<br><a href='https://nsis.ru' target='_blank'>nsis.ru/products/osago/check/</a>", "warning");
      return;
    }
    
    const tab = tabs[0];
    captchaImg.alt = "Считываем код...";
    
    chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        const img = document.querySelector('img[src*="captcha"], .captcha-image img, div[class*="captcha"] img, img[alt*="Капча"]');
        if (!img) return null;
        try {
          const canvas = document.createElement('canvas');
          canvas.width = img.naturalWidth || img.width;
          canvas.height = img.naturalHeight || img.height;
          const ctx = canvas.getContext('2d');
          ctx.drawImage(img, 0, 0);
          return canvas.toDataURL('image/png');
        } catch (e) {
          return img.src;
        }
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
        const refreshBtn = Array.from(document.querySelectorAll('button, span, a, svg'))
          .find(el => el.innerText?.includes('Обновить') || el.className?.toString().includes('refresh'));
        if (refreshBtn) refreshBtn.click();
        else location.reload();
      }
    });
    setTimeout(initExtension, 1200);
  } catch (error) {
    console.error('Ошибка при обновлении капчи:', error);
  }
}

// ИСПРАВЛЕНО: Добавлен await перед Tesseract.createWorker
async function recognizeCaptcha() {
  try {
    const captchaImg = document.getElementById('captchaImg');
    if (!captchaImg || !captchaImg.src || captchaImg.src.startsWith('data:image/svg+xml')) return null;
    
    const worker = await Tesseract.createWorker('eng');
    await worker.setParameters({
      tessedit_char_whitelist: '0123456789',
    });
    
    const result = await worker.recognize(captchaImg.src);
    await worker.terminate();
    
    const recognized = result.data.text.replace(/[^0-9]/g, '').trim();
    console.log('Распознанная цифровая капча:', recognized);
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
    
    if (resultDiv) resultDiv.classList.add('hidden');
    if (loader) loader.classList.remove('hidden');

    if (!captchaWord) {
      showResult("🔍 Распознаю капчу...", "info");
      captchaWord = await recognizeCaptcha();
      if (!captchaWord) {
        if (loader) loader.classList.add('hidden');
        showResult("❌ Не удалось распознать капчу. Введите вручную.", "error");
        return;
      }
      captchaInput.value = captchaWord;
    }
    
    const tabs = await chrome.tabs.query({ url: CHECK_URL_PATTERN });
    if (!tabs || tabs.length === 0) {
      if (loader) loader.classList.add('hidden');
      showResult("❌ Вкладка НСИС была закрыта.", "error");
      return;
    }
    
    const tab = tabs[0];
    
    chrome.scripting.executeScript({
      target: { tabId: tab.id },
      args: [searchType, queryValue, captchaWord],
      func: (type, value, captcha) => {
        const simulateKeyboardType = (input, text) => {
          if (!input) return;
          input.focus();
          input.select();
          document.execCommand('insertText', false, ''); 
          document.execCommand('insertText', false, text);
          
          input.dispatchEvent(new Event('input', { bubbles: true }));
          input.dispatchEvent(new Event('change', { bubbles: true }));
          input.blur();
        };

        const allInputs = Array.from(document.querySelectorAll('input'));
        
        const regInput = allInputs.find(i => i.placeholder?.toLowerCase().includes('гос') || i.id?.toLowerCase().includes('reg') || i.name === 'regNum');
        const vinInput = allInputs.find(i => i.placeholder?.toLowerCase().includes('vin') || i.id?.toLowerCase().includes('vin') || i.name === 'vin');
        const bodyInput = allInputs.find(i => i.placeholder?.toLowerCase().includes('кузов') || i.id?.toLowerCase().includes('body') || i.name === 'bodyNum');
        const captchaInput = allInputs.find(i => i.placeholder?.toLowerCase().includes('картинки') || i.id?.toLowerCase().includes('captcha') || i.name === 'captcha');

        if (regInput) simulateKeyboardType(regInput, '');
        if (vinInput) simulateKeyboardType(vinInput, '');
        if (bodyInput) simulateKeyboardType(bodyInput, '');

        if (type === 'vin' && vinInput) simulateKeyboardType(vinInput, value);
        else if (type === 'regNumber' && regInput) simulateKeyboardType(regInput, value);
        else if (type === 'bodyNumber' && bodyInput) simulateKeyboardType(bodyInput, value);

        if (captchaInput) simulateKeyboardType(captchaInput, captcha);

        setTimeout(() => {
          const submitBtn = document.querySelector('button[type="submit"]') || 
                            Array.from(document.querySelectorAll('button'))
                            .find(b => b.innerText?.includes('Отправить') || b.innerText?.includes('Проверить'));
          if (submitBtn) {
            submitBtn.focus();
            submitBtn.click();
          }
        }, 500);
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

window.retryLastSearch = function() {
  const loader = document.getElementById('loader');
  const resultDiv = document.getElementById('result');
  if (resultDiv) resultDiv.classList.add('hidden');
  if (loader) loader.classList.remove('hidden');
  triggerSiteCaptchaRefresh();
  setTimeout(() => { handleSearch(); }, 1500);
};
