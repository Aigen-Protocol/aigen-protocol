// AIGEN background service worker (MV3)
// Currently minimal — kept for future use (e.g., context menus, cron checks)

chrome.runtime.onInstalled.addListener(() => {
  console.log('AIGEN extension installed');
});
