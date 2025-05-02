from typing import Dict, List, Optional
from datetime import datetime
from bson import ObjectId
from src.services.database_service import DatabaseService
from src.virtualization.digital_replica.schema_registry import SchemaRegistry
from src.digital_twin.core import DigitalTwin


class DTFactory:
    """Factory class for creating and managing Digital Twins"""

    def __init__(self, db_service: DatabaseService, schema_registry: SchemaRegistry):
        self.db_service = db_service
        self.schema_registry = schema_registry
        self._init_dt_collection()

    def create_dt(self, name: str, description: str = "") -> str:
        """
        Create a new Digital Twin

        Args:
            name: Name of the Digital Twin
            description: Optional description

        Returns:
            str: ID of the created Digital Twin
        """
        dt_data = {
            "_id": str(ObjectId()),
            "name": name,
            "description": description,
            "digital_replicas": [],  # List of DR references
            "services": [],  # List of service references
            "metadata": {
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "status": "active",
            },
        }

        try:
            dt_collection = self.db_service.db["digital_twins"]
            result = dt_collection.insert_one(dt_data)
            return str(result.inserted_id)
        except Exception as e:
            raise Exception(f"Failed to create Digital Twin: {str(e)}")

    def add_digital_replica(self, dt_id: str, dr_type: str, dr_id: str) -> None:
        """
        Add a Digital Replica reference to a Digital Twin

        Args:
            dt_id: Digital Twin ID
            dr_type: Type of Digital Replica
            dr_id: Digital Replica ID
        """
        try:
            dt_collection = self.db_service.db["digital_twins"]

            # Verify DR exists
            dr = self.db_service.get_dr(dr_type, dr_id)
            if not dr:
                raise ValueError(f"Digital Replica not found: {dr_id}")

            # Add DR reference
            dt_collection.update_one(
                {"_id": dt_id},
                {
                    "$push": {"digital_replicas": {"type": dr_type, "id": dr_id}},
                    "$set": {"metadata.updated_at": datetime.utcnow()},
                },
            )
        except Exception as e:
            raise Exception(f"Failed to add Digital Replica: {str(e)}")

    def _get_service_module_mapping(self) -> Dict[str, str]:
        """
        Returns a mapping of service names to their module paths
        """
        return {
            "AggregationService": "src.services.analytics",
            "TemperaturePredictionService": "src.services.TemperaturePredictionService",
        }

    def add_service(
        self, dt_id: str, service_name: str, service_config: Dict = None
    ) -> None:
        """
        Add a service reference to a Digital Twin

        Args:
            dt_id: Digital Twin ID
            service_name: Name of the service
            service_config: Optional service configuration
        """
        try:
            dt_collection = self.db_service.db["digital_twins"]

            # Ottieni il mapping dei moduli
            module_mapping = self._get_service_module_mapping()

            # Usa il mapping per trovare il modulo corretto
            if service_name not in module_mapping:
                raise ValueError(
                    f"Service {service_name} not configured in module mapping"
                )

            module_name = module_mapping[service_name]

            try:
                service_module = __import__(module_name, fromlist=[service_name])
                service_class = getattr(service_module, service_name)

                # Verifica che il servizio esista prima di aggiungerlo
                service = service_class()

                service_data = {
                    "name": service_name,
                    "config": service_config or {},
                    "status": "active",
                    "added_at": datetime.utcnow(),
                }

                dt_collection.update_one(
                    {"_id": dt_id},
                    {
                        "$push": {"services": service_data},
                        "$set": {"metadata.updated_at": datetime.utcnow()},
                    },
                )
            except (ImportError, AttributeError) as e:
                raise ValueError(
                    f"Failed to load service {service_name} from module {module_name}: {str(e)}"
                )

        except Exception as e:
            raise Exception(f"Failed to add service: {str(e)}")

    def get_dt(self, dt_id: str) -> Optional[Dict]:
        """
        Get a Digital Twin by ID

        Args:
            dt_id: Digital Twin ID

        Returns:
            Dict: Digital Twin data if found, None otherwise
        """
        try:
            dt_collection = self.db_service.db["digital_twins"]
            return dt_collection.find_one({"_id": dt_id})
        except Exception as e:
            raise Exception(f"Failed to get Digital Twin: {str(e)}")

    # def get_dt_by_name(self, name: str) -> Optional[Dict]:
    #     """
    #     Get a Digital Twin by name
    #
    #     Args:
    #         name: Digital Twin name
    #
    #     Returns:
    #         Dict: Digital Twin data if found, None otherwise
    #     """
    #     try:
    #         dt_collection = self.db_service.db["digital_twins"]
    #         return dt_collection.find_one({"name": name})
    #     except Exception as e:
    #         raise Exception(f"Failed to get Digital Twin: {str(e)}")

    def list_dts(self) -> List[Dict]:
        """
        List all Digital Twins

        Returns:
            List[Dict]: List of Digital Twins
        """
        try:
            dt_collection = self.db_service.db["digital_twins"]
            return list(dt_collection.find())
        except Exception as e:
            raise Exception(f"Failed to list Digital Twins: {str(e)}")

    # def update_dt(self, dt_id: str, update_data: Dict) -> None:
    #     """
    #     Update a Digital Twin
    #
    #     Args:
    #         dt_id: Digital Twin ID
    #         update_data: Data to update
    #     """
    #     try:
    #         dt_collection = self.db_service.db["digital_twins"]
    #
    #         # Ensure metadata.updated_at is set
    #         if "metadata" not in update_data:
    #             update_data["metadata"] = {}
    #         update_data["metadata"]["updated_at"] = datetime.utcnow()
    #
    #         result = dt_collection.update_one(
    #             {"_id": dt_id},
    #             {"$set": update_data}
    #         )
    #
    #         if result.matched_count == 0:
    #             raise ValueError(f"Digital Twin not found: {dt_id}")
    #
    #     except Exception as e:
    #         raise Exception(f"Failed to update Digital Twin: {str(e)}")

    # def delete_dt(self, dt_id: str) -> None:
    #     """
    #     Delete a Digital Twin
    #
    #     Args:
    #         dt_id: Digital Twin ID
    #     """
    #     try:
    #         dt_collection = self.db_service.db["digital_twins"]
    #         result = dt_collection.delete_one({"_id": dt_id})
    #
    #         if result.deleted_count == 0:
    #             raise ValueError(f"Digital Twin not found: {dt_id}")
    #
    #     except Exception as e:
    #         raise Exception(f"Failed to delete Digital Twin: {str(e)}")

    # def remove_digital_replica(self, dt_id: str, dr_id: str) -> None:
    #     """
    #     Remove a Digital Replica reference from a Digital Twin
    #
    #     Args:
    #         dt_id: Digital Twin ID
    #         dr_id: Digital Replica ID
    #     """
    #     try:
    #         dt_collection = self.db_service.db["digital_twins"]
    #
    #         dt_collection.update_one(
    #             {"_id": dt_id},
    #             {
    #                 "$pull": {
    #                     "digital_replicas": {
    #                         "id": dr_id
    #                     }
    #                 },
    #                 "$set": {
    #                     "metadata.updated_at": datetime.utcnow()
    #                 }
    #             }
    #         )
    #     except Exception as e:
    #         raise Exception(f"Failed to remove Digital Replica: {str(e)}")

    # def remove_service(self, dt_id: str, service_name: str) -> None:
    #     """
    #     Remove a service reference from a Digital Twin
    #
    #     Args:
    #         dt_id: Digital Twin ID
    #         service_name: Name of the service to remove
    #     """
    #     try:
    #         dt_collection = self.db_service.db["digital_twins"]
    #
    #         dt_collection.update_one(
    #             {"_id": dt_id},
    #             {
    #                 "$pull": {
    #                     "services": {
    #                         "name": service_name
    #                     }
    #                 },
    #                 "$set": {
    #                     "metadata.updated_at": datetime.utcnow()
    #                 }
    #             }
    #         )
    #     except Exception as e:
    #         raise Exception(f"Failed to remove service: {str(e)}")

    def _init_dt_collection(self) -> None:
        """Initialize the Digital Twin collection in MongoDB"""
        if not self.db_service.is_connected():
            raise ConnectionError("Database service not connected")

        try:
            db = self.db_service.db
            if "digital_twins" not in db.list_collection_names():
                db.create_collection("digital_twins")
                dt_collection = db["digital_twins"]
                dt_collection.create_index("name", unique=True)
                dt_collection.create_index("metadata.created_at")
                dt_collection.create_index("metadata.updated_at")
        except Exception as e:
            raise Exception(f"Failed to initialize DT collection: {str(e)}")

    def create_dt_from_data(self, dt_data: dict) -> DigitalTwin:
        """
        Create a DigitalTwin instance from database data with enhanced debugging
        """
        print("\n=== Creating DT Instance ===")
        try:
            # Create new DT instance
            dt = DigitalTwin()
            print(f"Created new DT instance for {dt_data.get('name', 'unnamed')}")

            # Add Digital Replicas
            for dr_ref in dt_data.get("digital_replicas", []):
                dr = self.db_service.get_dr(dr_ref["type"], dr_ref["id"])
                if dr:
                    dt.add_digital_replica(dr)
                    print(f"Added DR: {dr_ref['type']} - {dr_ref['id']}")

            # Add Services
            print("\nLoading services...")
            service_mapping = self._get_service_module_mapping()
            print(f"Service mapping: {service_mapping}")

            for service_data in dt_data.get("services", []):
                service_name = service_data["name"]
                print(f"\nProcessing service: {service_name}")

                if service_name in service_mapping:
                    try:
                        module_name = service_mapping[service_name]
                        print(f"Loading module: {module_name}")

                        service_module = __import__(
                            module_name, fromlist=[service_name]
                        )
                        print(f"Module loaded successfully")

                        service_class = getattr(service_module, service_name)
                        print(f"Got service class: {service_class}")

                        service = service_class()
                        print(f"Service instance created")

                        if hasattr(service, "configure") and "config" in service_data:
                            service.configure(service_data["config"])
                            print(f"Service configured with: {service_data['config']}")

                        dt.add_service(service)
                        print(f"Service added to DT")
                        print(f"Current DT services: {dt.list_services()}")
                    except Exception as e:
                        print(f"Error adding service {service_name}: {str(e)}")
                        print(f"Exception type: {type(e)}")
                else:
                    print(f"Warning: Service {service_name} not found in mapping")

            return dt

        except Exception as e:
            print(f"Error creating DT: {str(e)}")
            print(f"Exception type: {type(e)}")
            raise Exception(f"Failed to create DT from data: {str(e)}")

    def get_dt_instance(self, dt_id: str) -> Optional[DigitalTwin]:
        """
        Get a fully initialized DigitalTwin instance by ID

        Args:
            dt_id: Digital Twin ID

        Returns:
            Optional[DigitalTwin]: Digital Twin instance if found, None otherwise
        """
        try:
            # Get DT data from database
            dt_data = self.get_dt(dt_id)
            if not dt_data:
                return None

            # Create and return DT instance
            return self.create_dt_from_data(dt_data)

        except Exception as e:
            raise Exception(f"Failed to get DT instance: {str(e)}")
