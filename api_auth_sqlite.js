// api_auth_sqlite.js — 로그인 API (DB: building_manager.db) + 바이패스
const sqlite3 = require('better-sqlite3');
const crypto  = require('crypto');
const path    = require('path');

const DB_PATH    = path.join(__dirname, 'building_manager.db');
let db; // Lazy-load after first login attempt

function getDB() {
  try {
    if (!db) db = sqlite3(DB_PATH);
    return db;
  } catch(e) {
    console.error('[DATABASE] Failed to open building_manager.db:', e.message);
    db = null; // Prevent repeated failures in same request cycle
    return null;
  }
}

function sha256(str) { return crypto.createHash('sha256').update(str).digest('hex'); }

async function login(email, password) {
  const conn = getDB();
  if (!conn) return { error:'Database unavailable', success:false };

  try {
    const user = conn.prepare(
      'SELECT id, employee_no, password_hash, role_name FROM users WHERE employee_no = ? LIMIT 1'
    ).get(email.toLowerCase().trim());

    if (!user) return { error:'사번 또는 비밀번호 오류', success:false };
    const passHash = sha256(password);
    if (user.password_hash !== passHash) return { error:'사번 또는 비밀번호 오류', success:false };

    return { emp: user.employee_no, role: user.role_name, success:true };
  } catch(e) {
    console.error('[LOGIN] Error:', e.message);
    return { error:'Login server error', success:false };
  }
}

async function getMe(emp) {
  const conn = getDB();
  if (!conn) return { error:'Database unavailable', success:false };

  try {
    const user = conn.prepare(
      'SELECT employee_no, role_name FROM users WHERE employee_no = ?'
    ).get(emp);
    if (!user) return { error:'인증된 사용자가 없습니다', success:false };
    return { emp: user.employee_no, role: user.role_name, success:true };
  } catch(e) {
    console.error('[ME] Error:', e.message);
    return { error:'Server error', success:false };
  }
}

module.exports = { login, getMe, db };

