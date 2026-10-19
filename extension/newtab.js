(function () {
  var api = globalThis.chrome || globalThis.browser;
  var DEFAULT_URL = "http://127.0.0.1:8731/";

  function readUrl() {
    return new Promise(function (resolve) {
      if (!api || !api.storage) {
        resolve(DEFAULT_URL);
        return;
      }
      api.storage.local.get({ url: DEFAULT_URL }, function (items) {
        resolve((items && items.url) || DEFAULT_URL);
      });
    });
  }

  function showOffline(url) {
    document.getElementById("status").textContent = "The local work log server is not running.";
    var link = document.getElementById("open");
    link.href = url;
    link.textContent = url;
    document.getElementById("offline").hidden = false;
  }

  readUrl().then(function (url) {
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, 1500);
    fetch(url, { method: "GET", mode: "no-cors", cache: "no-store", signal: controller.signal })
      .then(function () {
        clearTimeout(timer);
        location.replace(url);
      })
      .catch(function () {
        clearTimeout(timer);
        showOffline(url);
      });
  });
})();
