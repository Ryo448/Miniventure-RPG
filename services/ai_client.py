import os
import re
import json
import requests
from config import Config
from services import file_storage


def call_ai(messages, adventure_code=None, max_tokens=None, temperature=None):
    url = Config.AI_API_URL
    api_key = Config.AI_API_KEY
    model = Config.AI_MODEL

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }

    payload = {
        'model': model,
        'messages': messages,
        'max_tokens': max_tokens or Config.AI_MAX_TOKENS,
        'temperature': temperature or Config.AI_TEMPERATURE
    }

    if getattr(Config, 'AI_DISABLE_THINKING', False):
        payload['chat_template_kwargs'] = {'enable_thinking': False}

    if adventure_code:
        file_storage.append_log(adventure_code, 'ai',
                                 f'Request: model={model}, messages={len(messages)}, max_tokens={payload["max_tokens"]}')

    try:
        timeout = max(30, getattr(Config, 'AI_TIMEOUT', 120))
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()
        result = response.json()

        content = result.get('choices', [{}])[0].get('message', {}).get('content', '')

        if adventure_code:
            file_storage.append_log(adventure_code, 'ai',
                                     f'Response: {content[:500]}...' if len(content) > 500 else f'Response: {content}')

        return content, None
    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        print(f'[ai_client] Erro na chamada da IA: {error_msg}', flush=True)
        if adventure_code:
            file_storage.append_log(adventure_code, 'ai', f'Error: {error_msg}')
        return None, error_msg


def parse_ai_json(content):
    if not content:
        return None

    import re
    original = content.strip()

    fenced = _extract_fenced_block(original)
    candidates = []
    if fenced is not None:
        candidates.append(fenced)
    candidates.append(original)

    for body in candidates:
        result = _try_parse_json_object(body)
        if isinstance(result, dict):
            return result

    return None


def _extract_fenced_block(content):
    fences = list(re.finditer(r'```', content))
    if len(fences) >= 2:
        first_open = fences[0].end()
        last_close = fences[-1].start()
        if last_close > first_open:
            body = content[first_open:last_close]
            body = body.lstrip('\n').strip()
            body = re.sub(r'^(?:json|JSON)\s*\n?', '', body).strip()
            body = body.strip('`').strip()
            for prefix in ('json', 'JSON'):
                if body.startswith(prefix):
                    body = body[len(prefix):].strip()
            return body
    return None


def _try_parse_json_object(content):
    content = content.strip('`').strip()
    for prefix in ('json', 'JSON'):
        if content.startswith(prefix):
            content = content[len(prefix):].strip()

    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    for opener, closer in ('{', '}'), ('[', ']'):
        start = content.find(opener)
        if start == -1:
            continue
        end = _find_balanced_end(content, start, opener, closer)
        if end != -1:
            candidate = content[start:end + 1]
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                fixed = _fix_json_string(candidate)
                try:
                    parsed = json.loads(fixed)
                    if isinstance(parsed, dict):
                        return parsed
                except json.JSONDecodeError:
                    pass
        else:
            # JSON truncado — tenta fechar brackets automaticamente
            candidate = _close_open_brackets(content[start:])
            if candidate:
                try:
                    parsed = json.loads(candidate)
                    if isinstance(parsed, dict):
                        print(f'[ai_client] JSON truncado recuperado ({len(candidate)} chars, brackets fechados automaticamente).', flush=True)
                        return parsed
                except json.JSONDecodeError:
                    fixed = _fix_json_string(candidate)
                    try:
                        parsed = json.loads(fixed)
                        if isinstance(parsed, dict):
                            print(f'[ai_client] JSON truncado recuperado após fix ({len(candidate)} chars).', flush=True)
                            return parsed
                    except json.JSONDecodeError:
                        pass
    return None


def _close_open_brackets(text):
    stack = []
    in_string = False
    escape = False
    for ch in text:
        if in_string:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch in '{[':
                stack.append('}' if ch == '{' else ']')
            elif ch in '}]':
                if stack:
                    stack.pop()
    if not stack:
        return text
    # se ainda dentro de string, fecha a string
    suffix = ''
    if in_string:
        suffix += '"'
    # fecha na ordem inversa
    for closer in reversed(stack):
        suffix += closer
    return text + suffix


def _find_balanced_end(text, start, opener, closer):
    depth = 0
    in_string = False
    escape = False
    i = start
    while i < len(text):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1


def _fix_json_string(text):
    if not text:
        return text
    parts = []
    i = 0
    n = len(text)
    in_string = False
    escape = False
    while i < n:
        ch = text[i]
        if in_string:
            if escape:
                parts.append(ch)
                escape = False
                i += 1
                continue
            if ch == '\\':
                parts.append(ch)
                escape = True
                i += 1
                continue
            if ch == '"':
                in_string = False
                parts.append(ch)
                i += 1
                continue
            if ch == '\n':
                parts.append('\\n')
                i += 1
                continue
            if ch == '\r':
                i += 1
                continue
            if ch == '\t':
                parts.append('\\t')
                i += 1
                continue
            parts.append(ch)
        else:
            if ch == '"':
                in_string = True
                parts.append(ch)
            elif ch == '\n':
                parts.append(' ')
            elif ch == '\r':
                pass
            elif ch == '\t':
                parts.append(' ')
            else:
                parts.append(ch)
        i += 1
    result = ''.join(parts)
    while '  ' in result:
        result = result.replace('  ', ' ')
    return result


def load_prompt(filename):
    from config import PROMPTS_DIR
    filepath = os.path.join(PROMPTS_DIR, filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ''

