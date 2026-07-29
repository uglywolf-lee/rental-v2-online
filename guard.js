// ===== 로그인 게이트 =====
// - 로그인(sessionStorage.loginOk) 없으면 → 로그인 페이지(index.html)로 강제 이동
// - 로그인은 됐으나 콘텐츠 페이지를 브라우저에서 단독(top-level)으로 연 경우 → 메인 셸(main.html)로 복귀
//   (콘텐츠 페이지는 반드시 로그인 → main.html 안에서만 열리도록 강제)
(function () {
  try {
    var ok = sessionStorage.getItem('loginOk') === 'true';
    if (!ok) {
      (window.top === window.self ? window : window.top).location.replace('index.html');
      return;
    }
    if (window.top === window.self) {
      // 단독으로 직접 열린 콘텐츠 페이지 → 로그인 후의 정상 진입점(main.html)으로 되돌림
      window.location.replace('main.html');
    }
  } catch (e) {
    location.replace('index.html');
  }
})();

// ===== 작업 로그용: 모든 저장/수정 요청에 로그인한 사용자(_actor)를 자동 첨부 =====
(function () {
  if (window.__actorPatched) return;
  window.__actorPatched = true;
  var _fetch = window.fetch;
  window.fetch = function (url, opt) {
    try {
      var u = String(url || '');
      if (opt && String(opt.method || '').toUpperCase() === 'POST'
          && u.indexOf('/api/v1/') === 0 && typeof opt.body === 'string'
          && (opt.headers && String(JSON.stringify(opt.headers)).indexOf('json') > -1)) {
        var d = JSON.parse(opt.body);
        if (d && typeof d === 'object' && !d._actor) {
          d._actor = (sessionStorage.getItem('userEmp') || '') +
                     (sessionStorage.getItem('userRole') ? ' (' + sessionStorage.getItem('userRole') + ')' : '');
          opt = Object.assign({}, opt, { body: JSON.stringify(d) });
        }
      }
    } catch (e) { /* 실패해도 원래 요청 그대로 진행 */ }
    return _fetch(url, opt);
  };
})();
