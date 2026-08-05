// ===== 로그인 게이트 =====
// - 로그인(sessionStorage.loginOk) 없으면 → 로그인 페이지(index.html)로 강제 이동
// - 로그인은 됐으나 콘텐츠 페이지를 브라우저에서 단독(top-level)으로 연 경우 → 메인 셸(main.html)로 복귀
//   (콘텐츠 페이지는 반드시 로그인 → main.html 안에서만 열리도록 강제)
(function () {
  var DOC_KEY = '_docWinPass';        // 서류 창에 로그인 상태를 건네주는 임시 표
  var DOC_TTL = 12 * 60 * 60 * 1000;  // 12시간이 지나면 무효

  // 서류 보기 창인가?
  var isDocWin = /doc_viewer\.html/i.test(location.pathname);
  // 휴대폰 화면인가? — 보기 전용이며 혼자 열리는 것이 정상입니다 (main.html 로 되돌리지 않음)
  var isMobile = /mobile\.html/i.test(location.pathname);

  // 휴대폰은 로그인을 오래 기억합니다.
  //   홈 화면 아이콘으로 열 때마다 비밀번호를 물으면 어르신이 쓰실 수 없습니다.
  //   보기 전용 화면이고, 자기 폰이며, Tailscale 안에서만 닿는 주소라서 이렇게 둡니다.
  //   컴퓨터(서류 창)는 예전대로 12시간입니다.
  var TTL = isMobile ? 30 * 24 * 60 * 60 * 1000 : DOC_TTL;

  try {
    var ok = sessionStorage.getItem('loginOk') === 'true';

    // 새 창은 sessionStorage 를 물려받지 못하는 브라우저가 있다.
    // 서류 창에 한해 아래 3가지를 차례로 시도해 로그인 상태를 이어받는다.
    if (!ok && (isDocWin || isMobile)) {

      // ① 창을 띄운 쪽(부모 창)에서 직접 읽어온다 — 가장 확실하다
      try {
        var op = window.opener;
        if (op && op.sessionStorage && op.sessionStorage.getItem('loginOk') === 'true') {
          sessionStorage.setItem('loginOk', 'true');
          sessionStorage.setItem('userEmp',  op.sessionStorage.getItem('userEmp')  || '');
          sessionStorage.setItem('userRole', op.sessionStorage.getItem('userRole') || '');
          ok = true;
        }
      } catch (eA) {}

      // ② 주소에 함께 실어 보낸 표를 쓴다 (부모 창을 못 읽는 경우)
      if (!ok) {
        try {
          var tk = new URLSearchParams(location.search).get('t');
          if (tk) {
            var d = JSON.parse(decodeURIComponent(escape(atob(tk))));
            if (d && d.ts && (Date.now() - d.ts) < TTL) {
              sessionStorage.setItem('loginOk', 'true');
              sessionStorage.setItem('userEmp',  d.emp  || '');
              sessionStorage.setItem('userRole', d.role || '');
              ok = true;
            }
          }
        } catch (eB) {}
      }

      // ③ 브라우저에 남겨둔 표를 쓴다
      if (!ok) {
        try {
          var pass = JSON.parse(localStorage.getItem(DOC_KEY) || 'null');
          if (pass && pass.ts && (Date.now() - pass.ts) < TTL) {
            sessionStorage.setItem('loginOk', 'true');
            sessionStorage.setItem('userEmp',  pass.emp  || '');
            sessionStorage.setItem('userRole', pass.role || '');
            ok = true;
          }
        } catch (eC) {}
      }
    }

    if (!ok) {
      // 서류 창이 못 들어왔을 때는 조용히 로그인 화면으로 보내지 않고
      // '무엇이 막았는지'를 화면에 보여 준다. (원인을 못 찾으면 고칠 수가 없다)
      if (isDocWin) {
        var why = [];
        try { why.push('내 세션: ' + (sessionStorage.getItem('loginOk') || '없음')); }
        catch (x) { why.push('내 세션: 읽기 실패 (' + x.message + ')'); }
        try {
          why.push('부모 창: ' + (!window.opener ? '연결 없음'
                   : (window.opener.sessionStorage.getItem('loginOk') || '로그인값 없음')));
        } catch (x) { why.push('부모 창: 읽기 막힘 (' + x.message + ')'); }
        try {
          why.push('주소표: ' + (new URLSearchParams(location.search).get('t') ? '있음(해독 실패)' : '없음'));
        } catch (x) { why.push('주소표: 확인 실패'); }
        try {
          why.push('브라우저표: ' + (localStorage.getItem('_docWinPass') ? '있음(기한 지남)' : '없음'));
        } catch (x) { why.push('브라우저표: 읽기 막힘 (' + x.message + ')'); }

        document.addEventListener('DOMContentLoaded', function () {
          document.body.innerHTML =
            '<div style="font-family:Malgun Gothic,sans-serif;padding:30px;line-height:1.9;color:#222">'
            + '<h2 style="color:#c92a2a;margin-bottom:14px">서류 창이 로그인 상태를 확인하지 못했습니다</h2>'
            + '<p>아래 내용을 그대로 알려 주시면 원인을 잡을 수 있습니다.</p>'
            + '<pre style="background:#f8f9fa;border:1px solid #dee2e6;border-radius:6px;'
            + 'padding:14px;font-size:.9rem;white-space:pre-wrap">' + why.join('\n') + '</pre>'
            + '<p style="margin-top:16px"><a href="index.html" style="color:#5a2fb8">로그인 화면으로 가기</a></p>'
            + '</div>';
        });
        return;
      }
      (window.top === window.self ? window : window.top).location.replace('index.html');
      return;
    }

    // 로그인된 상태라면, 서류 창이 이어받을 수 있게 표를 갱신해 둔다
    if (!isDocWin) {
      try {
        localStorage.setItem(DOC_KEY, JSON.stringify({
          ts:   Date.now(),
          emp:  sessionStorage.getItem('userEmp')  || '',
          role: sessionStorage.getItem('userRole') || ''
        }));
      } catch (e3) {}
    }

    // 서류 보기 창과 휴대폰 화면은 일부러 혼자 여는 것이므로 main.html 로 되돌리지 않는다
    if (window.top === window.self && !isDocWin && !isMobile) {
      // 단독으로 직접 열린 콘텐츠 페이지 → 로그인 후의 정상 진입점(main.html)으로 되돌림
      window.location.replace('main.html');
    }
  } catch (e) {
    // 서류 창에서는 조용히 로그인 화면으로 보내지 않는다.
    // 여기로 오면 위 코드 어딘가에서 오류가 난 것이므로 그 내용을 그대로 보여 준다.
    if (isDocWin) {
      var msg = (e && (e.message || e.name)) || String(e);
      document.addEventListener('DOMContentLoaded', function () {
        document.body.innerHTML =
          '<div style="font-family:Malgun Gothic,sans-serif;padding:30px;line-height:1.9;color:#222">'
          + '<h2 style="color:#c92a2a;margin-bottom:14px">서류 창에서 오류가 났습니다</h2>'
          + '<pre style="background:#f8f9fa;border:1px solid #dee2e6;border-radius:6px;'
          + 'padding:14px;font-size:.9rem;white-space:pre-wrap">' + msg + '</pre>'
          + '<p style="margin-top:16px"><a href="index.html" style="color:#5a2fb8">로그인 화면으로 가기</a></p>'
          + '</div>';
      });
      return;
    }
    location.replace('index.html');
  }
})();

// ===== 계약 만기일 계산 (자동 연장 반영) =====
//
// 깔세처럼 매달 내면서 계속 사는 계약이 있습니다. 나갈 때까지 이어집니다.
// 계약서에 적힌 종료일은 그대로 두되, [자동 연장]이 켜져 있으면
// 그 종료일을 **달 단위로 밀어** '이번 기간 종료일'을 계산해서 씁니다.
//
// 이 규칙은 여기 한 곳에만 둡니다. 화면마다 복사하면 언젠가 서로 어긋납니다.
//
//   contractEnd(계약)        → 이번 기간 종료일 'YYYY-MM-DD' (없으면 '')
//   contractAlive(계약)      → 오늘 기준으로 살아있는 계약인가
//   contractExtended(계약)   → 연장 중인가 (원래 종료일이 지났는가)
(function () {
  function ymd(d) {
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0')
                           + '-' + String(d.getDate()).padStart(2, '0');
  }
  function today() { return ymd(new Date()); }

  // 달을 더합니다. 말일 처리 주의 — 1월 31일 + 1개월은 2월 31일이 없으므로 2월 28일로 둡니다.
  function addMonths(iso, n) {
    var p = String(iso).substring(0, 10).split('-');
    var y = Number(p[0]), m = Number(p[1]) - 1, day = Number(p[2]);
    m += n;
    var y2 = y + Math.floor(m / 12), m2 = ((m % 12) + 12) % 12;
    var last = new Date(y2, m2 + 1, 0).getDate();
    return ymd(new Date(y2, m2, Math.min(day, last)));
  }

  function addDays(iso, n) {
    var p = String(iso).substring(0, 10).split('-');
    return ymd(new Date(Number(p[0]), Number(p[1]) - 1, Number(p[2]) + n));
  }

  // 이번 기간 종료일.
  //   계약 기간은 '시작일 + n개월 − 1일' 로 셉니다. (1월 15일 시작 → 2월 14일 종료 = 딱 한 달)
  //   그래서 연장도 종료일이 아니라 **시작일**을 기준으로 계산해야 합니다.
  //   종료일에 달을 더하면 월말 계약(1월 31일 시작 등)에서 하루씩 밀립니다.
  window.contractEnd = function (c) {
    var end   = String((c && c.end_date) || '').substring(0, 10);
    var start = String((c && c.start_date) || '').substring(0, 10);
    if (!end) return '';
    if (!c.auto_extend || String(c.auto_extend) === '0') return end;
    var t = today();
    if (end >= t) return end;                 // 아직 이번 기간 안이면 그대로

    if (!start) {                             // 시작일을 모르면 종료일 기준으로 (예비)
      var n0 = 0, cur0 = end;
      while (cur0 < t && n0 < 600) { n0++; cur0 = addMonths(end, n0); }
      return cur0;
    }
    // 자동 연장은 **한 달씩** 밉니다.
    //
    //   깔세 세입자는 보증금을 적게 내는 대신 월세를 더 내고, 원할 때 나갈 자유를 삽니다.
    //   그래서 매달 월세를 받을 때가 곧 '연장하시겠어요?' 하고 묻는 시점입니다.
    //   이번 기간 종료일이 **다음 월세 납입일 바로 전날**이 되어 사무실 흐름과 맞습니다.
    //
    //   서류상 기간(1년·2년)만큼 밀지 않는 이유: 정부가 달 단위 계약을 인정하지 않아
    //   계약서에는 길게 적을 뿐, 실제 약속은 한 달짜리이기 때문입니다.
    var k = 1, cur = end;
    while (cur < t && k < 600) { k++; cur = addDays(addMonths(start, k), -1); }
    return cur;
  };

  window.contractAlive = function (c) {
    var end = window.contractEnd(c);
    return !end || end >= today();
  };

  window.contractExtended = function (c) {
    if (!c || !c.auto_extend || String(c.auto_extend) === '0') return false;
    var orig = String(c.end_date || '').substring(0, 10);
    return !!orig && orig < today();
  };

  // ===== 수납 약정일 (매월 며칠에 월세를 받는가) =====
  //
  // 예전에는 모든 화면에 '매월 15일'이 글자로 박혀 있었습니다.
  // 실제로는 계약마다 다릅니다. 기준은 **계약 시작일과 같은 날**입니다.
  //   1월 15일에 시작했으면 매월 15일에 받습니다.
  //   이래야 '이번 기간 종료일(2월 14일)'이 다음 납입일 바로 전날이 되어 위 계산과 맞습니다.
  // 계약서에 다른 날로 적혀 있으면 계약 화면에서 그 날을 직접 넣습니다(contracts.pay_day).
  //
  //   contractPayDay(계약)     → 1~31 숫자. 알 수 없으면 0
  //   contractPayDayText(계약) → '매월 15일' 같은 표시용 글자. 모르면 '-'
  window.contractPayDay = function (c) {
    var d = Number(c && c.pay_day) || 0;          // 계약서에 따로 적어 둔 날이 우선
    if (d >= 1 && d <= 31) return d;
    var p = String((c && c.start_date) || '').substring(0, 10).split('-');
    var s = Number(p[2]) || 0;                    // 없으면 계약 시작일과 같은 날
    return (s >= 1 && s <= 31) ? s : 0;
  };

  window.contractPayDayText = function (c) {
    var d = window.contractPayDay(c);
    return d ? ('매월 ' + d + '일') : '-';
  };
})();


// ===== 서류 보기 창 (계약서 · 신분증) =====
// 어느 화면에서든 이름이나 호실을 누르면 별도 창으로 원본이 뜹니다.
// 모니터 옆에 띄워 두고 보면서 작업하라고 만든 창입니다.
//
// 쓰는 법 — 둘 중 아무거나
//   1) 코드에서 직접 :  onclick="openDocs(계약id)"   또는  openDocsByRoom('443')
//   2) 표시만 해두기  :  <td data-doc-room="443">443호</td>
//                       <td data-doc-contract="12">홍길동</td>
//      → 아래 자동 연결이 클릭을 알아서 잡아 줍니다. 각 화면을 고칠 필요가 없습니다.
(function () {
  if (window.__docViewerReady) return;
  window.__docViewerReady = true;

  function open(qs, key) {
    // 로그인 상태를 주소에도 함께 실어 보낸다 (새 창이 세션을 못 물려받는 브라우저 대비)
    var tk = '';
    try {
      tk = '&t=' + encodeURIComponent(btoa(unescape(encodeURIComponent(JSON.stringify({
        ts:   Date.now(),
        emp:  sessionStorage.getItem('userEmp')  || '',
        role: sessionStorage.getItem('userRole') || ''
      })))));
    } catch (e) {}

    // 주소창은 켜 둔다 — 문제가 생겼을 때 무엇이 열렸는지 눈으로 확인할 수 있어야 한다
    var w = window.open('doc_viewer.html?' + qs + tk, 'docwin_' + key,
                        'width=900,height=1000,menubar=no,toolbar=no');
    if (!w) {
      alert('팝업이 차단되어 서류 창을 열지 못했습니다.\n\n' +
            '브라우저 주소창 오른쪽의 차단 표시를 눌러\n이 사이트의 팝업을 허용해 주세요.');
      return null;
    }
    w.focus();
    return w;
  }

  // 계약 번호를 아는 경우
  window.openDocs = function (contractId) {
    if (!contractId) return;
    return open('contract=' + encodeURIComponent(contractId), contractId);
  };

  // 호실번호만 아는 경우 — 오늘 유효한 계약을 먼저 찾고, 공실이면 직전 계약을 보여줍니다
  window.openDocsByRoom = function (roomNo) {
    if (!roomNo) return;
    return open('room=' + encodeURIComponent(roomNo), 'r' + roomNo);
  };

  // 자동 연결: data-doc-room / data-doc-contract 가 붙은 칸이면 클릭을 잡아 준다
  document.addEventListener('click', function (e) {
    var el = e.target.closest ? e.target.closest('[data-doc-room],[data-doc-contract]') : null;
    if (!el) return;
    var cid = el.getAttribute('data-doc-contract');
    var rno = el.getAttribute('data-doc-room');
    if (cid) window.openDocs(cid);
    else if (rno) window.openDocsByRoom(rno);
  });

  // 누를 수 있는 칸이라는 걸 눈으로 알 수 있게 (각 화면에 CSS를 넣지 않아도 되도록)
  document.addEventListener('DOMContentLoaded', function () {
    var st = document.createElement('style');
    st.textContent =
      '[data-doc-room],[data-doc-contract]{cursor:pointer;color:#5a2fb8}' +
      '[data-doc-room]:hover,[data-doc-contract]:hover{background:#f3f0fa;text-decoration:underline}';
    document.head.appendChild(st);
  });
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
