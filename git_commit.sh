#!/bin/bash
# Release Gate — verify + odoo_check + git commit
cd "$(dirname "$0")"



echo ""
echo "========== [Gate] Step 1: Quality Gate (verify.py) =========="
python3 execution/scripts/verify.py
if [ $? -ne 0 ]; then
    echo "FAIL: Quality gate not passed. Fix errors and retry."
    exit 1
fi

echo ""
echo "========== [Gate] Step 2: Runtime Validation (odoo_check.py) =========="
python3 execution/scripts/odoo_check.py
if [ $? -ne 0 ]; then
    echo "FAIL: Runtime validation not passed. Fix errors and retry."
    exit 1
fi

echo ""
echo "========== [Gate] Step 2.5: Integration Tests (test_runner.py) =========="
python3 execution/scripts/test_runner.py
if [ $? -ne 0 ]; then
    echo "FAIL: Integration tests not passed. Fix errors and retry."
    exit 1
fi

echo ""
echo "========== [Gate] Step 3: Commit =========="
echo "Enter sprint description:"
read commit_msg
if [ -z "$commit_msg" ]; then
    echo "Empty description rejected"
    exit 1
fi

git add .
git commit -m "Sprint Iteration: $commit_msg"
git push origin main
echo "Commit done."
