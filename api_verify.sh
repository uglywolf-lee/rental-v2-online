#!/bin/bash
cd /Users/uglywolf/rental-v2-online
lsof -ti:8080 | xargs kill 2>/dev/null || true; sleep 1; node server.js &; sleep 2
echo "=== [1] static ===" && curl -sI http://127.0.0.1:8080/ | head -3
echo "=== [2] login valid ===" && curl -s -X POST http://127.0.0.1:8080/api/v1/auth/login -H "Content-Type: application/json" -d '{"emp":"EMP-001","password":"admin123"}'
echo "" && echo "=== [3] login error ===" && curl -s -X POST http://127.0.0.1:8080/api/v1/auth/login -H "Content-Type: application/json" -d '{"emp":"EMP-999","password":"wrong"}'
echo "" && echo "=== [4] auth/me ===" && curl -s http://127.0.0.1:8080/api/v1/auth/me -H "X-Emp: EMP-001"
echo "" && echo "DONE"
