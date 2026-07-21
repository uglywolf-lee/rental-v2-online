-- users 테이블 생성 + 초기 사용자 데이터
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  employee_no VARCHAR(20) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role_name VARCHAR(50) NOT NULL DEFAULT 'office_worker',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 초기 사용자 (비밀번호는 평문 저장 → 실제론 sha256 해싱 필요)
INSERT OR IGNORE INTO users (employee_no, password_hash, role_name) VALUES
  ('EMP-001', SHA2('admin123', 256), 'super_admin'),
  ('EMP-002', SHA2('staff123', 256), 'office_worker'),
  ('maint-01', SHA2('maint123', 256), 'maintenance_staff');
