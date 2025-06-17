from datetime import datetime
from pprint import pprint
from src.virtualization.digital_replica.dr_factory import DRFactory  # usa il tuo path reale
import os

def main():
    yaml_path = "src/virtualization/templates/user.yaml"  # cambia se necessario

    if not os.path.exists(yaml_path):
        print(f"❌ File YAML non trovato: {yaml_path}")
        return

    # Istanzia la factory
    factory = DRFactory(yaml_path)

    # Verifica che initialization sia caricata
    init_values = factory.schema.get("schemas", {}).get("validations", {}).get("initialization", {})
    print("🔍 Initialization caricata dal file YAML:")
    pprint(init_values)

    # Crea un DR utente con solo il profilo richiesto
    new_user = factory.create_dr("user", {
        "profile": {
            "username": "test_user",
            "password": "hashed_password_123",
            "telegram_id": 123456
        }
    })

    print("\n✅ Digital Replica creato con successo:")
    pprint(new_user)

    # Verifica i campi inizializzati
    print("\n🧪 Campi inizializzati automaticamente:")
    print("- owned_gardens:", new_user.get("data", {}).get("owned_gardens"))
    print("- owned_plants:", new_user.get("data", {}).get("owned_plants"))
    print("- last_login:", new_user.get("data", {}).get("last_login"))
    print("- metadata.status:", new_user.get("metadata", {}).get("status"))

if __name__ == "__main__":
    main()
