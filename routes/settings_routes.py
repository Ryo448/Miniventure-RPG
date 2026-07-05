from flask import Blueprint, request, jsonify
from config import Config

settings_routes = Blueprint('settings_routes', __name__)


@settings_routes.route('/api/settings', methods=['GET'])
def get_settings():
    cfg = Config.get_ai_config()
    # mask the key for display: show only last 4 chars
    key = cfg['AI_API_KEY']
    cfg['AI_API_KEY_MASKED'] = '•' * max(0, len(key) - 4) + key[-4:] if len(key) >= 4 else '••••'
    cfg['AI_API_KEY'] = key
    return jsonify(cfg)


@settings_routes.route('/api/settings', methods=['PUT'])
def update_settings():
    data = request.get_json() or {}

    api_url = data.get('apiUrl')
    api_key = data.get('apiKey')
    model = data.get('model')
    max_tokens = data.get('maxTokens')
    temperature = data.get('temperature')
    scene_size = data.get('sceneSize')
    ai_timeout = data.get('aiTimeout')
    disable_thinking = data.get('disableThinking')

    # empty api_key means "keep current"
    if api_key == '':
        api_key = None

    Config.set_ai_config(
        api_url=api_url,
        api_key=api_key,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        scene_size=scene_size,
        ai_timeout=ai_timeout,
        disable_thinking=disable_thinking
    )

    return jsonify(Config.get_ai_config())
