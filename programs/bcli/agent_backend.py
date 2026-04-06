import sys
import json
import os
import re
import time
from pathlib import Path

# SET UP ENVIRONMENT
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
os.chdir(project_root)

# REDIRECT STDOUT/STDERR
real_stdout = sys.__stdout__
sys.stdout = open(os.devnull, 'w')
sys.stderr = open(os.devnull, 'w')

# Suppress all logging
import logging
logging.root.handlers = []
logging.root.setLevel(logging.CRITICAL)

def send_msg(type, content, extra=None):
    msg = {"type": type, "content": content}
    if extra:
        msg["extra"] = extra
    # Clean output for C bridge JSON extraction
    clean_content = str(content).replace("\"", "'").replace("\n", " ")
    msg["content"] = clean_content
    if extra:
        msg["extra"] = str(extra).replace("\"", "'").replace("\n", " ")

    real_stdout.write(json.dumps(msg) + "\n")
    real_stdout.flush()

def run_agentic_loop(query, jarvis):
    nlu = jarvis.nlu_service
    prompts = jarvis.prompts

    # SYSTEM PROMPT for the agent loop
    system_prompt = prompts.get("interpreter_system_prompt", {}).get("prompt", "You are an agent.")
    system_prompt += "\nYou can use local tools to perform tasks. If you need to read a file, use Python."

    history = jarvis.long_memory.get_recent_history(10)

    current_prompt = f"{system_prompt}\n\nUser Query: {query}"

    for iteration in range(5): # Limit to 5 steps
        send_msg("thought", f"Reasoning... (Step {iteration + 1})")

        try:
            response = nlu.ask_llm(current_prompt, history)
        except Exception as e:
            send_msg("error", f"LLM Error: {str(e)}")
            break

        # Parse response for thought and action
        code_match = re.search(r"```python\n(.*?)```", response, re.DOTALL)

        if code_match:
            code = code_match.group(1)
            # Find the thought (text before code block)
            thought = response.split("```python")[0].strip()
            if thought: send_msg("thought", thought)

            send_msg("code", code, extra="python")

            # Execute code
            from butler.interpreter import interpreter
            success, output = interpreter.run("python", code)

            if success:
                send_msg("shell", output)
                # Feedback loop
                current_prompt = f"Previous step result: {output}\n\nPlease continue or finish the task."
                history.append({"role": "assistant", "content": response})
                history.append({"role": "user", "content": f"Output: {output}"})
            else:
                send_msg("error", output)
                current_prompt = f"Previous step failed with error: {output}\n\nPlease fix and try again."
                history.append({"role": "assistant", "content": response})
                history.append({"role": "user", "content": f"Error: {output}"})
        else:
            send_msg("text", response)
            break

if __name__ == "__main__":
    if len(sys.argv) < 3: sys.exit(1)
    query = sys.argv[2]

    send_msg("thought", "Butler Brain Initializing...")

    try:
        from butler.butler_app import Jarvis
        jarvis = Jarvis(headless=True)

        # Determine if we should use the full agentic loop or just a direct tool
        history = jarvis.long_memory.get_recent_history(5)
        nlu_result = jarvis.nlu_service.extract_intent(query, history)
        intent = nlu_result.get("intent", "unknown")

        # If it's a simple tool call, handle it directly for speed
        if intent == "get_weather":
            city = nlu_result.get("entities", {}).get("city", "北京")
            from package.network.weather import get_weather_from_web
            send_msg("tool", "weather", extra=f"city={city}")
            send_msg("text", str(get_weather_from_web(city)))
        elif intent == "translate_op":
             text = nlu_result.get("entities", {}).get("text", "")
             from package.document.translators import translate_text
             send_msg("tool", "translation")
             send_msg("text", translate_text(text))
        else:
            # Fallback to the agentic loop
            run_agentic_loop(query, jarvis)

    except Exception as e:
        send_msg("error", str(e))
