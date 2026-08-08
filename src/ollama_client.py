"""The call_model script for the run loop with
one HTTP POST to the local Ollama server."""

import json
import urllib.request

OLLAMA_URL = "http://{host}:11434/api/generate"
TIMEOUT_SECONDS = 1800   # the 7B model measured at 11 minutes 46 seconds so this gives around 2.5x headroom


def call_ollama(prompt, config):
    """POST one prompt, return Ollama's raw response dict.

    Generation settings are passed explicitlysince Ollama's default num_ctx is
    4096 and it truncates generation with no error or warning"""

    payload = {
        "model": config["model"],
        "prompt": prompt,
        "stream": False, # stream: false waits for generation to finish and sends one object with the complete output dict

        # the settings
        "options": {
            "num_ctx": config["num_ctx"],
            "num_predict": config["num_predict"],
            "temperature": config["temperature"],
            "seed": config["seed"],
        },
    }

    url = OLLAMA_URL.format(host=config.get("ollama_host", "localhost")) #checks if the config json has an ollama_host field and if it doesn't it defaults and returns localhost
    
    request = urllib.request.Request(
        url, # destination
        data=json.dumps(payload).encode(), # the data (configuration) in bytes
        headers={"Content-Type": "application/json"}, # tells Ollama to read the body in JSON format
    )

    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read()) # response.read() reades the returned body as bytes and then json.loads parses it back to a dict