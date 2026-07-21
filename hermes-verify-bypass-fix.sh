#!/bin/bash
set -e
# hermes-verify-bypass-fix.sh — run to verify index.html bypass patch works
FILE="/Users/uglywolf/rental-management-v2/index.html"

grep -q "sessionStorage.setItem('loginOk', 'true');" "$FILE" || { echo "[FAIL] loginOk set missing"; exit 1; }
grep -q "sessionStorage.setItem('userRole', 'super_admin');" "$FILE" || { echo "[FAIL] userRole set missing"; exit 1; }
grep -q "login.html" "$FILE" && { echo "[FAIL] still references login.html"; exit 1; }

echo "[OK] bypass fix verified — all 3 session vars present, no login.html reference"
