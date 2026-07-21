// api_auth.js — 로그인 API 엔드포인트 (작은 파일 분리)
const crypto = require('crypto');

// --- 로컬 사용자 정의 (첫 개발용) ---
const USERS_DB = [
  { employee_no: 'EMP-001', password_hash: crypto.createHash('sha256').update('admin123').digest('hex'), role_name: 'super_admin' },
  { employee_no: 'EMP-002', password_hash: crypto.createHash('sha256').update('staff123').digest('hex'), role_name: 'office_worker' },
  { employee_no: 'maint-01', password_hash: crypto.createHash('sha256').update('maint123').digest('hex'), role_name: 'maintenance_staff' }
];

function sha256(str) { return crypto.createHash('sha256').update(str).digest('hex'); }

function login(username, password) {
  const hash = sha256(password);
  for (const u of USERS_DB) {
    if (u.employee_no.toLowerCase() === username.toLowerCase() && u.password_hash === hash.toLowerCase()) {
      return { emp: u.employee_no, role: u.role_name, success: true };
    }
  }
  return { error: '사번 또는 비밀번호 오류', success: false };
}

function getMe(emp) {
  const user = USERS_DB.find(u => u.employee_no.toLowerCase() === emp.toLowerCase());
  if (!user) return { error: '인증된 사용자가 없습니다', success: false };
  return { emp: user.employee_no, role: user.role_name, success: true };
}

module.exports = { login, getMe };
