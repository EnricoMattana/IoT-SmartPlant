from pydantic import ValidationError
from src.virtualization.digital_replica.dr_factory import DRFactory
from datetime import datetime
# Path assoluto o relativo al tuo YAML
yaml_path = "src/virtualization/templates/plant.yaml"

# Dati volutamente invalidi
initial_data = {
    "profile": {
        "name": "Test",
        "owner_id": "user",
        "outdoor": "1",              # ❌ bool
        "location": "cagliari",         # ❌ enum
        "auto_watering": 1,      # ❌ bool
        "garden_id": "21"
    },
    "metadata": {
        "status": "unknown"           # ❌ enum
    },
    "data": {
        "measurements": [
            {
                "type": "go",      # ❌ enum
                "value": 2,      # ❌ float
                "timestamp": datetime.utcnow()  # ❌ datetime
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
