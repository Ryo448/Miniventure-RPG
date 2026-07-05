import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from config import Config, ADVENTURES_DIR, LOCAL_CHARACTERS_DIR
from services.file_storage import ensure_dir
from services.socket_service import socketio
from routes.page_routes import page_routes
from routes.adventure_routes import adventure_routes
from routes.character_routes import character_routes
from routes.catalog_routes import catalog_routes
from routes.game_routes import game_routes
from routes.ai_enhance_routes import ai_enhance_routes
from routes.settings_routes import settings_routes
from routes.socket_routes import register_socket_handlers


def create_app():
    app = Flask(__name__,
                template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
                static_folder=os.path.join(os.path.dirname(__file__), 'static'))

    app.config.from_object(Config)

    ensure_dir(ADVENTURES_DIR)
    ensure_dir(LOCAL_CHARACTERS_DIR)

    app.register_blueprint(page_routes)
    app.register_blueprint(adventure_routes)
    app.register_blueprint(character_routes)
    app.register_blueprint(catalog_routes)
    app.register_blueprint(game_routes)
    app.register_blueprint(ai_enhance_routes)
    app.register_blueprint(settings_routes)

    socketio.init_app(app)
    register_socket_handlers(socketio)

    @app.errorhandler(404)
    def not_found(e):
        return {'error': 'Recurso não encontrado.'}, 404

    @app.errorhandler(500)
    def server_error(e):
        return {'error': 'Erro interno do servidor.'}, 500

    return app


if __name__ == '__main__':
    app = create_app()
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
