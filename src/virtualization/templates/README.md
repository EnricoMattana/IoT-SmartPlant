# Digital Replica Template Creation Guidelines

## 1. Basic Structure Rules

A Digital Replica template MUST follow this exact structure:
```yaml
schemas:
  common_fields:     # Common fields across all sections
    [field definitions]
  entity:            # Entity-specific fields
    data:
      [field definitions]
  validations:       # Validation rules
    [validation definitions]
```

## 2. Field Definition Rules

### 2.1 Allowed Data Types
Only these data types are permitted:
- `str`: String values
- `int`: Integer values
- `float`: Floating point values
- `bool`: Boolean values
- `datetime`: Date and time values
- `Dict`: Dictionary/object values
- `List`: Array/list values
- `List[Dict]`: Array of dictionaries
- `List[str]`: Array of strings

### 2.2 Field Location Rules
- Identity fields (`_id`, `type`) MUST be defined in common_fields
- Profile fields MUST be defined in common_fields under 'profile'
- Metadata fields MUST be defined in common_fields under 'metadata'
- Data-related fields MUST be defined in entity.data

## 3. Validation Rules Structure

The validations section MUST contain these three subsections:

### 3.1 Mandatory Fields
```yaml
mandatory_fields:
  root:            # Fields required at root level
    - field1
    - field2
  metadata:        # Fields required in metadata
    - field1
  profile:         # Fields required in profile
    - field1
```

### 3.2 Type Constraints
```yaml
type_constraints:
  field_name:
    type: str|int|float|datetime|List[Dict]  # Required
    min: value                    # Optional, for numeric types
    max: value                    # Optional, for numeric types
    enum: [value1, value2, ...]  # Optional, for string types
    item_constraints:             # Required for List[Dict]
      required_fields: []         # Required fields in each dict
      type_mappings:             # Type for each field
        field1: type1
        field2: type2
```

### 3.3 Initialization
```yaml
initialization:
  field_name: default_value   # Default values for fields
```

## 4. Specific Field Rules

### 4.1 Common Fields Requirements
- MUST include `_id` and `type` fields
- MUST include a `metadata` section with at least:
  - `created_at` (datetime)
  - `updated_at` (datetime)
- IF profile is used, MUST define all profile fields under `profile` structure

### 4.2 Entity Data Requirements
- MUST be defined under `entity.data`
- MUST specify all possible data fields that the entity can have
- For measurement fields:
  - MUST define type constraints with required fields
  - MUST specify type mappings for all fields

## 5. Best Practices

### 5.1 Naming Conventions
- Use snake_case for all field names
- Field names should be descriptive and in English
- Avoid abbreviations unless widely recognized

### 5.2 Type Constraints
- Always define ranges for numeric fields where applicable
- Always define enums for fields with fixed possible values
- For List[Dict] fields, always specify complete item_constraints

### 5.3 Documentation
- Include descriptive comments for complex fields
- Document any special validation rules
- Document relationships between fields if they exist

## 6. Example Template

```yaml
schemas:
  common_fields:
    _id: str
    type: str
    profile:
      name: str
      surname: str
      birth_year: int
      gender: str
    metadata:
      created_at: datetime
      updated_at: datetime
      privacy_level: str

  entity:
    data:
      status: str
      measurements: List[Dict]
      sensors: List[str]

  validations:
    mandatory_fields:
      root:
        - _id
        - type
      profile:
        - name
        - surname
      metadata:
        - created_at
        - updated_at

    type_constraints:
      birth_year:
        type: int
        min: 1900
        max: 2024
      gender:
        type: str
        enum: ["male", "female", "other"]
      status:
        type: str
        enum: ["active", "inactive"]
        
      measurements:
        type: List[Dict]
        item_constraints:
          required_fields: ["type", "value", "timestamp"]
          type_mappings:
            type: str
            value: float
            timestamp: datetime

    initialization:
      status: "active"
      sensors: []
      measurements: []
      metadata:
        privacy_level: "private"
```

## 7. Validation Process

The template will be validated for:
1. Structural correctness (all required sections present)
2. Type validity (all specified types are allowed)
3. Constraint validity (all constraints are properly formatted)
4. Initialization validity (all default values match their type constraints)
5. Mandatory fields presence
6. Cross-field consistency (referenced fields exist)

## 8. Error Conditions

The template will be rejected if:
1. Any required section is missing
2. Any field uses an unsupported type
3. Any constraint references a non-existent field
4. Any initialization value violates its type constraints
5. Any mandatory field is not defined
6. Any List[Dict] field lacks proper item_constraints