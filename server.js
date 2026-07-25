const http = require('http');
const fs = require('fs');
const path = require('path');
const { login, getMe } = require('./api_auth_sqlite');

const PORT = 8899;
const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8'
};

const server = http.createServer((req, res) => {
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.url}`);
  
  // === API 라우팅 검출: /api/ 또는 /__ 로 시작하면 파일 serve 아님 ===
  const apiPath = req.url.split('?')[0]; // 쿼리 파라미터 제거한 경로만
  let pathname = apiPath; // 파일 serve时用 기본 값

  // 루트 경로('/') 접속 시 기본 파일 지정 & API 라우팅 분기
  if (apiPath.startsWith('/api/')) {
    const urlObj = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
    
    if (apiPath === '/api/v1/auth/login' && req.method === 'POST') {
      let body = '';
      req.on('data', chunk => { body += chunk.toString(); });
      req.on('end', () => {
        try {
          const { emp, password } = JSON.parse(body);
          const r = login(emp, password);
          if (r.success) {
            res.writeHead(200, {'Content-Type':'application/json; charset=utf-8'});
            res.end(JSON.stringify(r));
          } else {
            res.writeHead(401, {'Content-Type':'application/json; charset=utf-8'});
            res.end(JSON.stringify(r));
          }
        } catch(e) {
          res.writeHead(400, {'Content-Type':'application/json; charset=utf-8'});
          res.end(JSON.stringify({error:'JSON 파싱 실패', success:false}));
        }
      });
    } else if (apiPath === '/api/v1/auth/me' && req.method === 'GET') {
      const emp = req.headers['x-emp'] || '';
      const r = getMe(emp);
      if (r.success) res.writeHead(200, {'Content-Type':'application/json; charset=utf-8'});
      else res.writeHead(403, {'Content-Type':'application/json; charset=utf-8'});
      res.end(JSON.stringify(r));
    } else {
      res.writeHead(404, {'Content-Type':'application/json; charset=utf-8'});
      res.end(JSON.stringify({error:'API 엔드포인트 없음', path: apiPath}));
    }
  } else if (apiPath === '/') {
    pathname = '/index.html';
  }
  let filePath = '.' + pathname;
  
  // 파일이 존재하지 않는 경우 404 처리
  if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
    const fallbackFile = fs.existsSync('index.html') ? 'index.html' : 'login.html';
    fs.readFile(fallbackFile, (err, data) => {
      res.writeHead(404, {'Content-Type': 'text/html; charset=utf-8'});
      res.end(data ? data.toString() : '404 Not Found');
      console.log('[404] File Not found:', filePath);
    });
    return;
  }

  const ext = path.extname(filePath);
  const contentType = MIME_TYPES[ext] || 'application/octet-stream';
  
  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.writeHead(500, {'Content-Type': 'text/plain; charset=utf-8'});
      res.end('Server Error');
      console.log('[500] Server error:', filePath);
    } else {
      res.writeHead(200, {'Content-Type': contentType});
      res.end(data);
    }
  });
});

server.listen(PORT, () => {
  console.log(`========================================`);
  console.log(`✅ 부동산관리시스템 온라인 서버 기동 완료`);
  console.log(`🌐 주소: http://localhost:${PORT}`);
  console.log(`   (브라우저에서 접속하면 로그인 화면 나옵니다)`);
  console.log(`📁 폴더: ${process.cwd()}`);
  console.log(`✅ 바이폐스: http://localhost:${PORT}/?access=master_sys_884621`);
  console.log(`========================================`);
});
