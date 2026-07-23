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
