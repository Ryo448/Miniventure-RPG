from flask import Blueprint, jsonify
from services import catalog_service

catalog_routes = Blueprint('catalog_routes', __name__)


@catalog_routes.route('/api/catalog/weapons', methods=['GET'])
def get_weapons():
    weapons = catalog_service.get_weapons()
    return jsonify(weapons)


@catalog_routes.route('/api/catalog/abilities', methods=['GET'])
def get_abilities():
    abilities = catalog_service.get_abilities()
    return jsonify(abilities)


@catalog_routes.route('/api/catalog/races', methods=['GET'])
def get_races():
    races = catalog_service.get_races()
    return jsonify(races)
