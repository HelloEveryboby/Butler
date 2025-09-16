import os
import requests
import json

def smart_up_markdown(markdown_text: str) -> str:
    """
    Uses the DeepSeek API to improve a given string of Markdown text.
    """
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return "Error: DEEPSEEK_API_KEY environment variable not set."

    url = "https://api.deepseek.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    prompt = """\
You are a Markdown formatting expert. Your task is to take the user's input, which is a block of text converted to Markdown, and improve it.

Please apply the following improvements:
1.  **Fix Formatting:** Correct any broken or inconsistent Markdown syntax. Ensure headings, lists, tables, and code blocks are properly formatted.
2.  **Improve Readability:** Add paragraph breaks, bullet points, or other elements to make the text easier to read.
3.  **Correct Grammar and Spelling:** Fix any grammatical errors or typos in the text.
4.  **Maintain Content:** Do not add or remove any substantive information. The meaning and content of the original text must be preserved.

Return only the improved Markdown content, with no extra explanations or pleasantries.
"""

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": markdown_text}
        ],
        "max_tokens": 4096, # Allow for larger documents
        "temperature": 0.3   # A lower temperature for more deterministic output
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result_text = response.json()['choices'][0]['message']['content']

        # Clean up potential markdown code block fences from the response
        if result_text.strip().startswith("```markdown"):
            result_text = result_text.strip()[10:-4].strip()
        elif result_text.strip().startswith("```"):
             result_text = result_text.strip()[4:-4].strip()

        return result_text
    except requests.exceptions.RequestException as e:
        return f"Error calling DeepSeek API: {e}"
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        return f"Error parsing DeepSeek API response: {e}\nOriginal Response: {response.text}"
