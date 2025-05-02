from typing import Dict, List, Type, Any
from src.services.base import BaseService
from datetime import datetime


class DigitalTwin:
    """Core Digital Twin class that manages DRs and services"""

    def __init__(self):
        self.digital_replicas: List = []  # Lista di DR objects
        self.active_services: Dict = {}  # service_name -> service_instance

    def add_digital_replica(self, dr_instance: Any) -> None:
        """Aggiunge una Digital Replica al twin"""
        self.digital_replicas.append(dr_instance)

    def add_service(self, service):
        """Add a service to the DT"""
        if isinstance(service, type):
            # If a class is passed, instantiate it
            service = service()
        self.active_services[service.name] = service

    def list_services(self):
        """List all services"""
        return list(self.active_services.keys())

    def remove_service(self, service_name: str) -> None:
        """Rimuove un servizio attivo"""
        if service_name in self.active_services:
            del self.active_services[service_name]

    def get_dt_data(self):
        """Get all DT data including DRs"""
        return {"digital_replicas": self.digital_replicas}

    def execute_service(self, service_name: str, **kwargs):
        """Execute a named service with parameters"""
        if service_name not in self.active_services:
            raise ValueError(f"Service {service_name} not found")

        service = self.active_services[service_name]

        # Prepare data for service
        data = {"digital_replicas": self.digital_replicas}

        # Execute service with data and additional parameters
        return service.execute(data, **kwargs)

    # def execute_service_on_dr(self, service_name: str, dr: Any) -> Any:
    #     """
    #     Esegue un servizio sui dati di una DR
    #     """
    #     if dr not in self.digital_replicas:
    #         raise ValueError("This DR is not part of this Digital Twin")

    #     data = dr["data"]  # Assumiamo che la DR abbia un attributo data
    #     return self.execute_service(service_name, data)

    # def get_digital_replicas_by_type(self, dr_type: str):
    #     """Get all digital replicas of a specific type"""
    #     return [dr for dr in self.digital_replicas if dr['type'] == dr_type]

    # def print_replicas(self):
    #     """Print detailed information about all Digital Replicas"""
    #     print("\n" + "=" * 80)
    #     print(f"DIGITAL TWIN STATUS - Total Replicas: {len(self.digital_replicas)}")
    #     print("=" * 80)
    #
    #     for idx, dr in enumerate(self.digital_replicas, 1):
    #         print(f"\n{idx}. DIGITAL REPLICA: {dr['type'].upper()}")
    #         print("-" * 80)
    #
    #         # Print ID and Profile
    #         print(f"ID: {dr['id']}")
    #         print("\nPROFILE:")
    #         for key, value in dr['profile'].items():
    #             print(f"  {key}: {value}")
    #
    #         # Print Metadata
    #         print("\nMETADATA:")
    #         for key, value in dr['metadata'].items():
    #             if isinstance(value, datetime):
    #                 value = value.strftime("%Y-%m-%d %H:%M:%S")
    #             print(f"  {key}: {value}")
    #
    #         # Print Data
    #         print("\nDATA:")
    #         data = dr['data']
    #         for key, value in data.items():
    #             if key == 'measurements':
    #                 print("  measurements:")
    #                 for m in value:
    #                     timestamp = m['timestamp']
    #                     if isinstance(timestamp, datetime):
    #                         timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S")
    #                     print(f"    - type: {m['measure_type']}")
    #                     print(f"      value: {m['value']}")
    #                     print(f"      timestamp: {timestamp}")
    #             elif isinstance(value, dict):
    #                 print(f"  {key}:")
    #                 for k, v in value.items():
    #                     print(f"    {k}: {v}")
    #             elif isinstance(value, list):
    #                 print(f"  {key}: {', '.join(map(str, value))}")
    #             else:
    #                 print(f"  {key}: {value}")
    #
    #         print("-" * 80)
    #
    #     print("\n" + "=" * 80 + "\n")
