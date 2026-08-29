#!/bin/bash
cd "$(dirname "$0")/.."
R=./test_scripts/run_until_done.sh
echo "########## 1. full population, audit_v3 (the winner), 358 claims ##########"
$R 20 python3 test_scripts/run_audit_full.py ie_audit_v3 qwen2.5-coder:7b
echo "########## 2. finish the re-roll control ##########"
$R 20 python3 test_scripts/pilot_ie_audit.py control 55
echo "########## QUEUE DONE ##########"
