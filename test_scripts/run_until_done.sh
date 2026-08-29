#!/bin/bash
# Drive a runner until it completes, surviving the GPU box dropping off.
# usage: run_until_done.sh <max_attempts> <command...>
max=$1; shift
for i in $(seq 1 "$max"); do
  # wait for the host, HTTP only. ping is meaningless on that box.
  for w in $(seq 1 480); do
    if curl -s -m 8 -o /dev/null http://10.0.0.26:11434/api/tags; then break; fi
    sleep 30
  done
  echo "=== attempt $i/$max at $(date '+%H:%M:%S') ==="
  if "$@"; then
    echo "=== completed on attempt $i ==="; exit 0
  fi
  echo "=== attempt $i did not complete, retrying ==="
  sleep 30
done
echo "=== gave up after $max attempts ==="; exit 1
