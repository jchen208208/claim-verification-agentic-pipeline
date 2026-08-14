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

    request = urllib.request.Request(  # builds the HTTP request but does not send it yet
        DEEPSEEK_URL,
        data=json.dumps(payload).encode(),  # json.dumps turns the dict into a JSON string and .encode() turns that string into raw bytes
        headers={
            "Content-Type": "application/json",  # tells the deepseek server how to read these bytes
            "Authorization": f"Bearer {os.environ['DEEPSEEK_API_KEY']}",  # attaches the key to the request and deepseek server will authenticate it
        },
    )

    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response: # sending the HTTP request and creates a data stream you can read the response from. response is a file-like object that reads the body of an HTTP reply off a socket, and 'with' guarantees it gets closed 
        raw = json.loads(response.read())  # response.read() returns bytes, json.loads parses them back into a dict

    message = raw["choices"][0]["message"]

    # formats deepseek response dict to ollama response dict
    return {
        "response": message["content"],
        "prompt_eval_count": raw["usage"]["prompt_tokens"],
        "eval_count": raw["usage"]["completion_tokens"],
        "done_reason": raw["choices"][0]["finish_reason"], # square bracket means this field is always present and needed and if it doesn't exist, then raise error
        "thinking": message.get("reasoning_content"), # .get() return None instead because only reasoning models need htis field
        "model": raw.get("model"),
        "system_fingerprint": raw.get("system_fingerprint"),
    }