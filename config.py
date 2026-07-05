import os

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


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'miniventure-rpg-secret-key-change-me')

    AI_API_URL = _DEFAULTS['AI_API_URL']
    AI_API_KEY = _DEFAULTS['AI_API_KEY']
    AI_MODEL = _DEFAULTS['AI_MODEL']
    AI_MAX_TOKENS = _DEFAULTS['AI_MAX_TOKENS']
    AI_TEMPERATURE = _DEFAULTS['AI_TEMPERATURE']
    AI_TIMEOUT = _DEFAULTS['AI_TIMEOUT']
    AI_DISABLE_THINKING = _DEFAULTS['AI_DISABLE_THINKING']
    SCENE_SIZE = _DEFAULTS['SCENE_SIZE']

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
