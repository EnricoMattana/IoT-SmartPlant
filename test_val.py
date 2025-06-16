from pydantic import ValidationError
from src.virtualization.digital_replica.dr_factory import DRFactory

# Path assoluto o relativo al tuo YAML
yaml_path = "src/virtualization/templates/plant.yaml"

# Dati volutamente invalidi
initial_data = {
    "profile": {
        "name": "Test",
        "owner_id": "user",
        "outdoor": "True",              # ❌ bool
        "location": "True",         # ❌ enum
        "auto_watering": "1"       # ❌ bool
    },
    "metadata": {
        "status": "unknown"           # ❌ enum
    },
    "data": {
        "measurements": [
            {
                "type": "noise",      # ❌ enum
                "value": "2",      # ❌ float
                "timestamp": "oggi"   # ❌ datetime
            }
        ]
    }
}

if __name__ == "__main__":
    try:
        factory = DRFactory(yaml_path)
        dr = factory.create_dr("plant", initial_data)
        print("✅ DR creata correttamente (ma doveva fallire)")
    except ValidationError as ve:
        print("❌ Errore di validazione:")
        for err in ve.errors():
            loc = " → ".join(str(l) for l in err["loc"])
            print(f"- {loc} → {err['msg']}")
    except Exception as e:
        print(f"❌ Errore imprevisto: {e}")
