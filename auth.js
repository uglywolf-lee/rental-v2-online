(function () {
  var CFG = {
    sessionMs: 30 * 60 * 1000,
    validRoles: ['super_admin','office_worker','maintenance_staff']
  };

  function checkSession () {
    // 로그인 세션 체크 (미로그인 시 로그인 페이지로)
    if (!sessionStorage.getItem('loginOk')) {
      var cur = location.pathname.split('/').pop();
      if (cur && cur !== 'main.html' && cur !== 'index.html' && cur !== 'login.html') {
        location.href = 'index.html';
        return false;
      }
      return true;
    } else {
      var started = sessionStorage.getItem('_sess');
      if (!started) {
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
    sessionStorage.removeItem('loginOk');
    sessionStorage.removeItem('userRole');
    sessionStorage.removeItem('userEmp');
    sessionStorage.removeItem('_sess');
    location.href = 'index.html';
  };

  function getButtonsByRole (userRole) {
    if (CFG.validRoles.indexOf(userRole) === -1) userRole = 'super_admin';

    var allBtns = [
      {c:'RPT', l:'📋 금일 현황', p:'daily_report.html'},
      {c:'A', l:'부동산',     p:'interface-a.html'},
      {c:'B', l:'계약서',     p:'contract_master.html'},
      {c:'C', l:'계약자',     p:'contractor_roster.html'},
      {c:'D', l:'공과금검침',  p:'utility_bills.html'},
      {c:'E', l:'월세납부',   p:'monthly_rent_collection.html'},
      {c:'F', l:'유지보수',    p:'incidents_maintenance.html'},
      {c:'GHI', l:'통합대시보드', p:'g_h_i_dashboard.html'},
      {c:'K', l:'↩ 되돌리기',   p:'auditlog.html'},
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
    isCreatorBypass: false
  };

  checkSession();
})();
