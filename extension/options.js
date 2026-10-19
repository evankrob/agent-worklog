(function () {
  var api = globalThis.chrome || globalThis.browser;
  var DEFAULT_URL = "http://127.0.0.1:8731/";
  var input = document.getElementById("url");
  var message = document.getElementById("msg");
  var local = /^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?(\/.*)?$/;

  if (api && api.storage) {
    api.storage.local.get({ url: DEFAULT_URL }, function (items) {
      input.value = (items && items.url) || DEFAULT_URL;
    });
  }

  document.getElementById("save").addEventListener("click", function () {
    var url = (input.value || "").trim() || DEFAULT_URL;
    if (!local.test(url)) {
      message.textContent = "Use an http://127.0.0.1 or http://localhost URL.";
      return;
    }
    if (!api || !api.storage) {
      message.textContent = "Storage is not available in this browser.";
      return;
    }
    api.storage.local.set({ url: url }, function () {
      message.textContent = "Saved.";
    });
  });
})();
