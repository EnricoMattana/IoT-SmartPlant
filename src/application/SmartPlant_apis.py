from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from src.virtualization.digital_replica.dr_factory import DRFactory 
from bson import ObjectId 
smartplant_api = Blueprint('smartplant_api', __name__,url_prefix = '/api/smartplant')
def register_smartplant_blueprint(app): app.register_blueprint(smartplant_api)


@smartplant_api.route('/plants', methods=['POST'])
def create_plant():
    """
    Create a new plant.
    """
    try:
        data = request.get_json()
        print("=== DATA IN ENTRATA ===")
        print(data)
        # Load schema and create Digital Replica
        dr_factory = DRFactory('src/virtualization/templates/plant.yaml')
        plant = dr_factory.create_dr('plant', data)
        print("=== PRIMA DI SALVARE ===")
        print(plant)   # Vedi se qui c'è profile, metadata, etc.
        # Save to database
        db_service = current_app.config['DB_SERVICE']
        plant_id = db_service.save_dr("plant", plant)

        return jsonify({
            "status": "success",
            "message": "Plant created successfully",
            "plant_id": plant_id
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@smartplant_api.route('/plants', methods=['GET'])
def list_plants():
    """
    List all plants with optional filtering.
    """
    try:
        # Get query parameters
        filters = {}

        if request.args.get('status'):
            filters['metadata.status'] = request.args.get('status')

        # Query database with optional filters
        db_service = current_app.config['DB_SERVICE']
        plants = db_service.query_drs("plant", filters)

        return jsonify(plants), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

