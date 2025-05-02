from datetime import datetime
from typing import Dict, Any, Type, Optional, List, Union
from pydantic import BaseModel, create_model, Field, field_validator
import yaml
import uuid


class DRFactory:
    def __init__(self, schema_path: str):
        self.schema = self._load_schema(schema_path)
        if not self.schema or "schemas" not in self.schema:
            raise ValueError(f"Invalid schema structure in {schema_path}")

    def _load_schema(self, path: str) -> Dict:
        try:
            with open(path, "r") as file:
                return yaml.safe_load(file)
        except Exception as e:
            raise ValueError(f"Failed to load schema: {str(e)}")

    def _create_profile_model(self) -> Type[BaseModel]:
        """Create Pydantic model for profile section"""
        mandatory_fields = (
            self.schema["schemas"]
            .get("validations", {})
            .get("mandatory_fields", {})
            .get("profile", [])
        )
        type_constraints = (
            self.schema["schemas"].get("validations", {}).get("type_constraints", {})
        )

        field_definitions = {}
        profile_fields = self.schema["schemas"]["common_fields"].get("profile", {})

        for field_name, field_type in profile_fields.items():
            is_required = field_name in mandatory_fields
            constraints = {}

            if field_name in type_constraints:
                rules = type_constraints[field_name]
                if "min" in rules:
                    constraints["ge"] = rules["min"]
                if "max" in rules:
                    constraints["le"] = rules["max"]

            field_definitions[field_name] = (
                (
                    str
                    if field_type == "str"
                    else (
                        int
                        if field_type == "int"
                        else (
                            float
                            if field_type == "float"
                            else datetime if field_type == "datetime" else Any
                        )
                    )
                ),
                Field(None if not is_required else ..., **constraints),
            )

        model = create_model("Profile", **field_definitions)

        # Add enum validators where needed
        for field_name in field_definitions:
            if (
                field_name in type_constraints
                and "enum" in type_constraints[field_name]
            ):
                enum_values = type_constraints[field_name]["enum"]

                @field_validator(field_name)
                def validate_enum(value, field):
                    if value not in enum_values:
                        raise ValueError(f"{field.name} must be one of {enum_values}")
                    return value

                setattr(model, f"validate_{field_name}", validate_enum)

        return model

    def _create_data_model(self) -> Type[BaseModel]:
        """Create Pydantic model for data section"""
        type_constraints = (
            self.schema["schemas"].get("validations", {}).get("type_constraints", {})
        )
        data_fields = self.schema["schemas"].get("entity", {}).get("data", {})

        field_definitions = {}
        for field_name, field_type in data_fields.items():
            if field_type == "List[Dict]":
                field_definitions[field_name] = (
                    List[Dict[str, Any]],
                    Field(default_factory=list),
                )
            elif field_type == "List[str]":
                field_definitions[field_name] = (List[str], Field(default_factory=list))
            else:
                field_definitions[field_name] = (
                    (
                        str
                        if field_type == "str"
                        else (
                            int
                            if field_type == "int"
                            else float if field_type == "float" else Any
                        )
                    ),
                    Field(None),
                )

        model = create_model("Data", **field_definitions)

        # Add validators for fields that need them
        for field_name, field_type in data_fields.items():
            # Add enum validator if needed
            if (
                field_name in type_constraints
                and "enum" in type_constraints[field_name]
            ):
                enum_values = type_constraints[field_name]["enum"]

                @field_validator(field_name)
                def validate_enum(value, field):
                    if value not in enum_values:
                        raise ValueError(f"{field.name} must be one of {enum_values}")
                    return value

                setattr(model, f"validate_{field_name}", validate_enum)

            # Add List[Dict] validator if needed
            if field_type == "List[Dict]" and field_name in type_constraints:
                rules = type_constraints[field_name]
                if "item_constraints" in rules:
                    item_rules = rules["item_constraints"]
                    required_fields = item_rules.get("required_fields", [])
                    type_mappings = item_rules.get("type_mappings", {})

                    @field_validator(field_name)
                    def validate_list_items(value, field):
                        if not isinstance(value, list):
                            raise ValueError(f"{field.name} must be a list")

                        for idx, item in enumerate(value):
                            if not isinstance(item, dict):
                                raise ValueError(
                                    f"Item {idx} in {field.name} must be a dictionary"
                                )

                            missing = [f for f in required_fields if f not in item]
                            if missing:
                                raise ValueError(
                                    f"Missing required fields {missing} in item {idx}"
                                )

                            for key, expected_type in type_mappings.items():
                                if key in item:
                                    val = item[key]
                                    if expected_type == "datetime":
                                        if not isinstance(val, (datetime, str)):
                                            raise ValueError(
                                                f"Field {key} in item {idx} must be a datetime"
                                            )
                                    elif expected_type == "float":
                                        try:
                                            item[key] = float(val)
                                        except (TypeError, ValueError):
                                            raise ValueError(
                                                f"Field {key} in item {idx} must be a number"
                                            )
                        return value

                    setattr(model, f"validate_{field_name}", validate_list_items)

        return model

    def create_dr(self, dr_type: str, initial_data: Dict[str, Any]) -> Dict:
        """Create a new Digital Replica instance"""
        # Create Pydantic models for sections
        ProfileModel = self._create_profile_model()
        DataModel = self._create_data_model()

        # Initialize with required fields and defaults
        dr_dict = {
            "_id": str(uuid.uuid4()),  # Usiamo _id per MongoDB
            "type": dr_type,
            "metadata": {
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            },
            "data": {},  # Inizializziamo il contenitore data
        }

        # Apply initialization defaults
        init_values = (
            self.schema["schemas"].get("validations", {}).get("initialization", {})
        )
        for section, defaults in init_values.items():
            if section == "metadata":
                dr_dict["metadata"].update(defaults)
            elif section in [
                "status",
                "sensors",
                "devices",
                "medications",
                "measurements",
            ]:
                # Questi campi vanno dentro data
                dr_dict["data"][section] = defaults
            else:
                # Altri campi vanno nella root
                dr_dict[section] = defaults

        # Update with provided data and validate each section
        if "profile" in initial_data:
            profile = ProfileModel(**initial_data["profile"])
            dr_dict["profile"] = profile.model_dump(exclude_unset=True)

        if "data" in initial_data:
            data = DataModel(**{**dr_dict["data"], **initial_data["data"]})
            dr_dict["data"] = data.model_dump(exclude_unset=True)

        if "metadata" in initial_data:
            dr_dict["metadata"].update(initial_data["metadata"])

        return dr_dict

    def update_dr(self, dr: Dict[str, Any], updates: Dict[str, Any]) -> Dict:
        """Update an existing Digital Replica"""
        # Create Pydantic models
        ProfileModel = self._create_profile_model()
        DataModel = self._create_data_model()

        updated_dr = dr.copy()

        # Validate and apply updates section by section
        if "profile" in updates:
            current_profile = updated_dr.get("profile", {})
            profile = ProfileModel(**(current_profile | updates["profile"]))
            updated_dr["profile"] = profile.model_dump(exclude_unset=True)

        if "data" in updates:
            current_data = updated_dr.get("data", {})
            data = DataModel(**(current_data | updates["data"]))
            updated_dr["data"] = data.model_dump(exclude_unset=True)

        if "metadata" in updates:
            updated_dr["metadata"].update(updates["metadata"])

        # Update timestamp
        updated_dr["metadata"]["updated_at"] = datetime.utcnow()

        return updated_dr
