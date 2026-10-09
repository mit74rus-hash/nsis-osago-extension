// При клике на иконку расширения — открываем отдельное окно
chrome.action.onClicked.addListener((tab) => {
  chrome.windows.create({
    url: chrome.runtime.getURL('window.html'),
    type: 'popup',
    width: 400,
    height: 650,
    focused: true
  });
});