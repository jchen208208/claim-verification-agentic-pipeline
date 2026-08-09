"""The call_model script for condition 2 with one HTTPS POST to DeepSeek's API.
Returns a dict using Ollama's key names, so we don't have to change run_loop.py"""

import json
import os
import urllib.request

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
TIMEOUT_SECONDS = 1800


def call_deepseek(prompt, config):
    """post one prompt, return a dict in Ollama's response form."""

    payload = {
        "model": config["model"],
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "temperature": config["temperature"],
        "max_tokens": config["num_predict"],
    }

    request = urllib.request.Request(
        DEEPSEEK_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.environ['DEEPSEEK_API_KEY']}",
        },
    )

    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        raw = json.loads(response.read())

    message = raw["choices"][0]["message"]

    # formats deepseek response dict to ollama response dict
    return {
        "response": message["content"],
        "prompt_eval_count": raw["usage"]["prompt_tokens"],
        "eval_count": raw["usage"]["completion_tokens"],
        "done_reason": raw["choices"][0]["finish_reason"],
        "reasoning_content": message.get("reasoning_content"),
        "model": raw.get("model"),
        "system_fingerprint": raw.get("system_fingerprint"),
    }