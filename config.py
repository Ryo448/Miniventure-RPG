import os
import json

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')
PROMPTS_DIR = os.path.join(BASE_DIR, 'prompts')
SETTINGS_FILE = os.path.join(BASE_DIR, 'settings.json')


def get_documents_folder():
    try:
        import ctypes.wintypes
        CSIDL_PERSONAL = 5
        SHGFP_TYPE_CURRENT = 0
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(0, CSIDL_PERSONAL, 0, SHGFP_TYPE_CURRENT, buf)
        return buf.value
    except Exception:
        return os.path.join(os.path.expanduser('~'), 'Documents')


DOCUMENTS_DIR = get_documents_folder()
ADVENTURES_DIR = os.path.join(DOCUMENTS_DIR, 'Aventuras', 'aventuras')
LOCAL_CHARACTERS_DIR = os.path.join(DOCUMENTS_DIR, 'Personagens')


def _env(key, default):
    val = os.environ.get(key)
    return val if val is not None else default


_DEFAULTS = {
    'AI_API_URL': _env('AI_API_URL', 'http://localhost:3123/v1/chat/completions'),
    'AI_API_KEY': _env('AI_API_KEY', 'EuAmoORyo'),
    'AI_MODEL': _env('AI_MODEL', 'AgentBridge'),
    'AI_MAX_TOKENS': int(_env('AI_MAX_TOKENS', '2000')),
    'AI_TEMPERATURE': float(_env('AI_TEMPERATURE', '0.8')),
    'AI_TIMEOUT': int(_env('AI_TIMEOUT', '120')),
    'AI_DISABLE_THINKING': _env('AI_DISABLE_THINKING', 'false').lower() == 'true',
    'SCENE_SIZE': _env('SCENE_SIZE', 'unlimited'),
}


def load_settings():
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_settings(data):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'miniventure-rpg-secret-key-change-me')

    _settings = load_settings()

    AI_API_URL = _settings.get('AI_API_URL', _DEFAULTS.get('AI_API_URL'))
    AI_API_KEY = _settings.get('AI_API_KEY', _DEFAULTS.get('AI_API_KEY'))
    AI_MODEL = _settings.get('AI_MODEL', _DEFAULTS.get('AI_MODEL'))
    AI_MAX_TOKENS = _settings.get('AI_MAX_TOKENS', _DEFAULTS.get('AI_MAX_TOKENS'))
    AI_TEMPERATURE = _settings.get('AI_TEMPERATURE', _DEFAULTS.get('AI_TEMPERATURE'))
    AI_TIMEOUT = _settings.get('AI_TIMEOUT', _DEFAULTS.get('AI_TIMEOUT'))
    AI_DISABLE_THINKING = _settings.get('AI_DISABLE_THINKING', _DEFAULTS.get('AI_DISABLE_THINKING'))
    SCENE_SIZE = _settings.get('SCENE_SIZE', _DEFAULTS.get('SCENE_SIZE'))

    @staticmethod
    def set_ai_config(api_url=None, api_key=None, model=None, max_tokens=None, temperature=None, scene_size=None, ai_timeout=None, disable_thinking=None):
        changed = False
        if api_url is not None:
            Config.AI_API_URL = api_url
            Config._settings['AI_API_URL'] = api_url
            changed = True
        if api_key is not None:
            Config.AI_API_KEY = api_key
            Config._settings['AI_API_KEY'] = api_key
            changed = True
        if model is not None:
            Config.AI_MODEL = model
            Config._settings['AI_MODEL'] = model
            changed = True
        if max_tokens is not None:
            Config.AI_MAX_TOKENS = int(max_tokens)
            Config._settings['AI_MAX_TOKENS'] = int(max_tokens)
            changed = True
        if temperature is not None:
            Config.AI_TEMPERATURE = float(temperature)
            Config._settings['AI_TEMPERATURE'] = float(temperature)
            changed = True
        if scene_size is not None:
            Config.SCENE_SIZE = scene_size
            Config._settings['SCENE_SIZE'] = scene_size
            changed = True
        if ai_timeout is not None:
            Config.AI_TIMEOUT = int(ai_timeout)
            Config._settings['AI_TIMEOUT'] = int(ai_timeout)
            changed = True
        if disable_thinking is not None:
            Config.AI_DISABLE_THINKING = bool(disable_thinking)
            Config._settings['AI_DISABLE_THINKING'] = bool(disable_thinking)
            changed = True
        if changed:
            save_settings(Config._settings)

    @staticmethod
    def get_ai_config():
        return {
            'AI_API_URL': Config.AI_API_URL,
            'AI_API_KEY': Config.AI_API_KEY,
            'AI_MODEL': Config.AI_MODEL,
            'AI_MAX_TOKENS': Config.AI_MAX_TOKENS,
            'AI_TEMPERATURE': Config.AI_TEMPERATURE,
            'AI_TIMEOUT': Config.AI_TIMEOUT,
            'AI_DISABLE_THINKING': Config.AI_DISABLE_THINKING,
            'SCENE_SIZE': Config.SCENE_SIZE
        }
