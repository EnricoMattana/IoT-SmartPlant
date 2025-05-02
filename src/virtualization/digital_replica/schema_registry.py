from typing import Dict, Any
import yaml


class SchemaRegistry:
    def __init__(self):
        self.schemas = {}

    def load_schema(self, schema_type: str, yaml_path: str) -> None:
        """Load schema from YAML file"""
        try:
            with open(yaml_path, "r") as file:
                raw_schema = yaml.safe_load(file)

            if not raw_schema or "schemas" not in raw_schema:
                raise ValueError(f"Invalid schema structure in {yaml_path}")

            # Convert YAML schema to MongoDB validation schema
            validation_schema = self._convert_yaml_to_mongodb_schema(
                raw_schema["schemas"]
            )
            self.schemas[schema_type] = validation_schema

        except Exception as e:
            raise ValueError(f"Failed to load schema from {yaml_path}: {str(e)}")

    def _convert_yaml_to_mongodb_schema(self, yaml_schema: Dict) -> Dict:
        """Convert YAML schema format to MongoDB $jsonSchema format"""

        def convert_type(yaml_type: str) -> str:
            """Convert YAML type to MongoDB BSON type"""
            type_mapping = {
                "str": "string",
                "int": "int",
                "float": "double",
                "bool": "bool",
                "datetime": "date",
                "Dict": "object",
                "List": "array",
            }
            return type_mapping.get(yaml_type, yaml_type)

        def process_field(field_def):
            """Process a field definition from YAML to MongoDB format"""
            if isinstance(field_def, str):
                return {"bsonType": convert_type(field_def)}
            elif isinstance(field_def, dict):
                return {
                    "bsonType": "object",
                    "properties": {k: process_field(v) for k, v in field_def.items()},
                }
            elif isinstance(field_def, list):
                # Handle List[Dict] case
                return {"bsonType": "array"}
            return field_def

        # Process common fields
        properties = {}
        if "common_fields" in yaml_schema:
            for field_name, field_def in yaml_schema["common_fields"].items():
                properties[field_name] = process_field(field_def)

        # Process entity fields
        if "entity" in yaml_schema and "data" in yaml_schema["entity"]:
            properties["data"] = process_field(yaml_schema["entity"]["data"])

        # Process validations if present
        required_fields = []
        if "validations" in yaml_schema:
            if "required" in yaml_schema["validations"]:
                required_fields.extend(yaml_schema["validations"]["required"])

        # Build final schema
        validation_schema = {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["_id", "type"] + required_fields,
                "properties": {
                    "_id": {"bsonType": "string"},
                    "type": {"bsonType": "string"},
                    **properties,
                },
            }
        }

        return validation_schema

    def get_collection_name(self, schema_type: str) -> str:
        """Get collection name for schema type"""
        return f"{schema_type}_collection"

    def get_validation_schema(self, schema_type: str) -> Dict:
        """Get validation schema for type"""
        if schema_type not in self.schemas:
            raise ValueError(f"Schema not found for type: {schema_type}")
        return self.schemas[schema_type]
