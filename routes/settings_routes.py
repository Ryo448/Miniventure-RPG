from flask import Blueprint, jsonify
from config import Config

settings_routes = Blueprint('settings_routes', __name__)


@settings_routes.route('/api/settings', methods=['GET'])
def get_settings():
    return jsonify(Config.get_ai_config())
