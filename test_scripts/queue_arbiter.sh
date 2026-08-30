#!/bin/bash
# Full arbiter test set. Each step retries through a box drop.
cd "$(dirname "$0")/.."
R=./test_scripts/run_until_done.sh
echo "##### 1. arbiter_v1, 200-claim head-to-head #####"
$R 30 python3 test_scripts/run_arbiter.py arbiter_v1 qwen2.5-coder:7b 200
echo "##### 2. arbiter_v2, 200-claim head-to-head #####"
$R 30 python3 test_scripts/run_arbiter.py arbiter_v2 qwen2.5-coder:7b 200
echo "##### 3. arbiter_v1, FULL disagreement set, 575 #####"
$R 30 python3 test_scripts/run_arbiter.py arbiter_v1 qwen2.5-coder:7b
echo "##### 4. arbiter_v2, FULL disagreement set, 575 #####"
$R 30 python3 test_scripts/run_arbiter.py arbiter_v2 qwen2.5-coder:7b
echo "##### QUEUE DONE #####"
