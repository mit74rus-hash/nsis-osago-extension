function waitForResult(tabId, loader, attempts = 0) {
  const maxAttempts = 30;
  const delay = 500;
  
  if (attempts >= maxAttempts) {
    if (loader) loader.classList.add('hidden');
    showResult("⏱ Время ожидания истекло. Проверьте вкладку НСИС вручную.", "warning", true);
    return;
  }
  
  setTimeout(() => {
    chrome.scripting.executeScript({
      target: { tabId: tabId },
      func: () => {
        const bodyText = document.body.innerText;
        const modal = document.querySelector('[class*="modal"], [class*="dialog"], [role="dialog"]');
        const modalText = modal ? modal.innerText : '';
        
        if (modalText.includes("попробуйте еще раз") || bodyText.includes("попробуйте еще раз") ||
            modalText.includes("попробуйте ещё раз") || bodyText.includes("попробуйте ещё раз")) {
          return { status: "server_error", message: "Сервер НСИС перегружен" };
        }
        if (modalText.includes("пике активности") || bodyText.includes("пике активности")) {
          return { status: "server_busy", message: "Сервер на пике активности" };
        }
        if (bodyText.includes("Неверный код") || bodyText.includes("Капча введена неверно") || bodyText.includes("неверно")) {
          return { status: "captcha_error" };
        }
        if (bodyText.includes("Данные о полисах ОСАГО") || bodyText.includes("Статус договора") || bodyText.includes("Серия полиса")) {
          return { status: "success", text: document.body.innerText };
        }
        if (bodyText.includes("не найден") || bodyText.includes("Полис отсутствует") || bodyText.includes("Ничего не найдено")) {
          return { status: "not_found" };
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
            showResult("❌ Неверный код капчи! Картинка обновлена.", "error");
            initExtension();
            break;
          case "server_error":
          case "server_busy":
            if (loader) loader.classList.add('hidden');
            showResult("⚠️ Проблема на сервере НСИС. Повторите запрос.", "warning", true);
            break;
          case "success":
            if (loader) loader.classList.add('hidden');
            renderPremiumCard(res.text);
            break;
          case "not_found":
            if (loader) loader.classList.add('hidden');
            showResult("⚠️ Страховка ОСАГО не найдена в базе НСИС.", "warning");
            initExtension();
            break;
          default:
            waitForResult(tabId, loader, attempts + 1);
        }
      }
    });
  }, delay);
}
