#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

REPORT="evidence/package_audit_$(date -u +%Y%m%d_%H%M%S).txt"

PASS=0
WARN=0
FAIL=0

exec > >(tee "$REPORT") 2>&1

pass() {
    echo "[PASS] $1"
    PASS=$((PASS + 1))
}

warn() {
    echo "[WARN] $1"
    WARN=$((WARN + 1))
}

fail() {
    echo "[FAIL] $1"
    FAIL=$((FAIL + 1))
}

echo "=================================================="
echo "SW103K ERIC VALIDATION PACKAGE AUDIT"
echo "=================================================="
date -u
echo "Directory: $ROOT"
echo

# 1. Required directory structure
echo "===== 1. REQUIRED DIRECTORIES ====="

for d in bin evidence scripts test-data tests VPS1 VPS2; do
    if [[ -d "$d" ]]; then
        pass "Directory exists: $d"
    else
        fail "Missing directory: $d"
    fi
done

# 2. Required files
echo
echo "===== 2. REQUIRED FILES ====="

REQUIRED_FILES=(
    README.md
    RUNBOOK.md
    SPECIFICATION.md
    SECURITY.md
    bin/sw103k_proxy
    bin/libsw103kcompress.so
    bin/license_server.py
    scripts/generate_test_data.py
    scripts/verify_test_data.sh
    VPS1/config.env
    VPS1/01_prepare_source.sh
    VPS1/03_run_client.sh
    VPS2/config.env
    VPS2/run_receiver.sh
    VPS2/02_collect_receiver.sh
    tests/eric_test_client.py
    test-data/manifest.json
    test-data/SHA256SUMS
)

for f in "${REQUIRED_FILES[@]}"; do
    if [[ ! -f "$f" ]]; then
        fail "Missing required file: $f"
    elif [[ ! -s "$f" ]]; then
        fail "Empty required file: $f"
    else
        pass "Present and non-empty: $f"
    fi
done

# 3. Inventory all files
echo
echo "===== 3. COMPLETE FILE INVENTORY ====="

find . -type f \
    ! -path "./.git/*" \
    ! -path "./evidence/package_audit_*" \
    -printf '%M %10s bytes %p\n' | sort

# 4. Empty files
echo
echo "===== 4. EMPTY FILE CHECK ====="

while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    fail "Empty file: $f"
done < <(find . -type f -empty \
    ! -path "./evidence/package_audit_*")

# 5. Shell syntax
echo
echo "===== 5. SHELL SCRIPT SYNTAX ====="

while IFS= read -r f; do
    if bash -n "$f"; then
        pass "Shell syntax valid: $f"
    else
        fail "Shell syntax error: $f"
    fi
done < <(find . -type f -name "*.sh" \
    ! -path "./evidence/*")

# 6. Python syntax
echo
echo "===== 6. PYTHON SYNTAX ====="

while IFS= read -r f; do
    if python3 -m py_compile "$f" 2>&1; then
        pass "Python syntax valid: $f"
    else
        fail "Python syntax error: $f"
    fi
done < <(find . -type f -name "*.py" \
    ! -path "./evidence/*")

# 7. Executable permissions
echo
echo "===== 7. EXECUTABLE PERMISSIONS ====="

for f in \
    scripts/*.sh \
    VPS1/*.sh \
    VPS2/*.sh \
    audit_package.sh
do
    [[ -f "$f" ]] || continue

    if [[ -x "$f" ]]; then
        pass "Executable: $f"
    else
        warn "Not executable: $f"
    fi
done

# 8. Binary architecture and dependencies
echo
echo "===== 8. BINARY INSPECTION ====="

for f in bin/sw103k_proxy bin/libsw103kcompress.so; do
    if [[ ! -f "$f" ]]; then
        continue
    fi

    file "$f"

    if ! file "$f" | grep -qE 'ELF'; then
        fail "Not an ELF binary: $f"
        continue
    fi

    if command -v ldd >/dev/null 2>&1; then
        echo "--- Dependencies: $f ---"
        ldd "$f"

        if ldd "$f" 2>&1 | grep -q 'not found'; then
            fail "Missing binary dependency: $f"
        else
            pass "No missing shared libraries reported: $f"
        fi
    fi
done

# 9. Test workload integrity
echo
echo "===== 9. TEST DATA INTEGRITY ====="

if [[ -f scripts/verify_test_data.sh ]]; then
    if bash scripts/verify_test_data.sh; then
        pass "Test data verification completed"
    else
        fail "Test data verification failed"
    fi
else
    warn "Test-data verification script missing"
fi

# 10. Check SHA256 manifests
echo
echo "===== 10. CHECKSUM MANIFESTS ====="

if [[ -f test-data/SHA256SUMS ]]; then
    if (cd test-data && sha256sum -c SHA256SUMS); then
        pass "Test-data SHA256 manifest verified"
    else
        fail "Test-data SHA256 verification failed"
    fi
else
    fail "test-data/SHA256SUMS missing"
fi

if [[ -f SHA256SUMS ]]; then
    if sha256sum -c SHA256SUMS; then
        pass "Root SHA256 manifest verified"
    else
        warn "Root SHA256 manifest needs review"
    fi
else
    warn "Root SHA256SUMS not present"
fi

# 11. Detect placeholders and unfinished code
echo
echo "===== 11. PLACEHOLDER AND TODO SCAN ====="

if grep -RniE \
    'TODO|FIXME|PLACEHOLDER|IMPLEMENT ME|NOT IMPLEMENTED|YOUR_SERVER_IP|YOUR_IP_HERE|CHANGE_ME|EXAMPLE_ONLY' \
    README.md RUNBOOK.md SPECIFICATION.md SECURITY.md \
    scripts VPS1 VPS2 tests 2>/dev/null
then
    warn "Potential unfinished content found; inspect matches above"
else
    pass "No obvious placeholder markers found"
fi

# 12. Check important script contents
echo
echo "===== 12. REQUIRED FUNCTIONALITY CHECK ====="

check_pattern() {
    local file="$1"
    local pattern="$2"
    local description="$3"

    if [[ -f "$file" ]] && grep -qE "$pattern" "$file"; then
        pass "$description"
    else
        fail "$description missing in $file"
    fi
}

check_pattern VPS2/run_receiver.sh 'sw103k_proxy|TCP|10300' \
    "Receiver startup references actual server"
check_pattern VPS2/run_receiver.sh 'ss|netstat|10300' \
    "Receiver readiness check"
check_pattern VPS1/03_run_client.sh 'sha256sum|sha256' \
    "Sender SHA256 verification"
check_pattern VPS1/03_run_client.sh '10300' \
    "Sender references TCP port 10300"
check_pattern VPS1/03_run_client.sh 'python|client' \
    "Sender invokes a client implementation"
check_pattern VPS2/02_collect_receiver.sh 'log|evidence|sha256' \
    "Receiver evidence collection"
check_pattern README.md '10300' \
    "README documents protocol port"
check_pattern RUNBOOK.md 'VPS1|VPS2' \
    "Runbook documents both VPS machines"

# 13. Network configuration
echo
echo "===== 13. CONFIGURATION REVIEW ====="

for f in VPS1/config.env VPS2/config.env; do
    if [[ -f "$f" ]]; then
        echo "--- $f ---"
        sed -E 's/(KEY|SECRET|TOKEN|PASSWORD)=.*/\1=[REDACTED]/I' "$f"
    fi
done

# 14. Final result
echo
echo "=================================================="
echo "FINAL PACKAGE AUDIT"
echo "=================================================="
echo "PASS: $PASS"
echo "WARN: $WARN"
echo "FAIL: $FAIL"
echo "REPORT: $REPORT"

if (( FAIL > 0 )); then
    echo "RESULT: FAIL - package needs corrections"
    exit 1
elif (( WARN > 0 )); then
    echo "RESULT: REVIEW REQUIRED - warnings remain"
    exit 2
else
    echo "RESULT: STRUCTURAL CHECKS PASSED"
    exit 0
fi
