from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from bson import ObjectId

# Create blueprints for different API groups
dt_api = Blueprint('dt_api', __name__, url_prefix='/api/dt')
dr_api = Blueprint('dr_api', __name__, url_prefix='/api/dr')
dt_management_api = Blueprint('dt_management_api', __name__, url_prefix='/api/dt-management')


# Digital Twin APIs
@dt_api.route('/', methods=['POST'])
def create_digital_twin():
    """Create a new Digital Twin"""
    try:
        data = request.get_json()
        required_fields = ['name', 'description']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400

        dt_id = current_app.config['DT_FACTORY'].create_dt(
            name=data['name'],
            description=data['description']
        )
        return jsonify({'dt_id': dt_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@dt_api.route('/<dt_id>', methods=['GET'])
def get_digital_twin(dt_id):
    """Get Digital Twin details"""
    try:
        dt = current_app.config['DT_FACTORY'].get_dt(dt_id)
        if not dt:
            return jsonify({'error': 'Digital Twin not found'}), 404
        return jsonify(dt), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@dt_api.route('/', methods=['GET'])
def list_digital_twins():
    """List all Digital Twins"""
    try:
        dts = current_app.config['DT_FACTORY'].list_dts()
        return jsonify(dts), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Generic Digital Replica APIs
@dr_api.route('/<dr_type>/<dr_id>', methods=['GET'])
def get_digital_replica(dr_type, dr_id):
    """Get Digital Replica details"""
    try:
        dr = current_app.config['DB_SERVICE'].get_dr(dr_type, dr_id)
        if not dr:
            return jsonify({'error': 'Digital Replica not found'}), 404
        return jsonify(dr), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Digital Twin Management APIs
@dt_management_api.route('/assign/<dt_id>', methods=['POST'])
def assign_dr_to_dt(dt_id):
    """Assign a Digital Replica to a Digital Twin"""
    try:
        data = request.get_json()
        required_fields = ['dr_type', 'dr_id']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400

        current_app.config['DT_FACTORY'].add_digital_replica(
            dt_id,
            data['dr_type'],
            data['dr_id']
        )

        return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@dt_management_api.route('/stats/<dt_id>', methods=['GET'])
def get_dt_stats(dt_id):
    """Get statistics from a Digital Twin's services"""
    try:
        dt = current_app.config['DT_FACTORY'].get_dt(dt_id)
        if not dt:
            return jsonify({'error': 'Digital Twin not found'}), 404

        params = request.args.to_dict()
        dr_type = params.get('dr_type')
        measure_type = params.get('measure_type')

        stats = current_app.config['DT_FACTORY'].get_dt_instance(dt_id).execute_service(
            'AggregationService',
            dr_type=dr_type,
            attribute=measure_type
        )

        return jsonify(stats), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@dt_api.route('/<dt_id>/services', methods=['POST'])
def add_service_to_dt(dt_id):
    """Add a service to Digital Twin"""
    try:
        data = request.get_json()
        if not data or 'name' not in data:
            return jsonify({'error': 'Missing service name'}), 400

        current_app.config['DT_FACTORY'].add_service(
            dt_id=dt_id,
            service_name=data['name'],
            service_config=data.get('config', {})
        )
        return jsonify({'status': 'success', 'message': f"Service {data['name']} added"}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def register_api_blueprints(app):
    """Register all API blueprints with the Flask app"""
    app.register_blueprint(dt_api)
    app.register_blueprint(dr_api)
    app.register_blueprint(dt_management_api)

