from typing import List, Dict
from datetime import datetime
from .base import BaseService

from typing import List, Dict, Any
from datetime import datetime
from .base import BaseService
import statistics


class AggregationService(BaseService):
    """Service for aggregating measurements across different Digital Replicas"""

    def execute(self, data: Dict, dr_type: str = None, attribute: str = None) -> Dict:
        """
        Execute aggregation on measurements from specified DR type

        Args:
            data: Dictionary containing the DT data including all DRs
            dr_type: Type of DR to aggregate (e.g., 'bottle', 'device')
            attribute: Specific measurement type to aggregate (e.g., 'temperature')
        """
        if not data or 'digital_replicas' not in data:
            raise ValueError("Invalid data: missing digital replicas")

        # Filter DRs by type if specified
        drs = [dr for dr in data['digital_replicas'] if dr_type is None or dr['type'] == dr_type]

        if not drs:
            return {"error": f"No digital replicas found of type {dr_type}"}

        # Collect all measurements
        all_measurements = []
        for dr in drs:
            if 'data' in dr and 'measurements' in dr['data']:
                measurements = dr['data']['measurements']
                if attribute:
                    # Filter measurements by attribute
                    measurements = [m for m in measurements
                                    if m['measure_type'] == attribute]
                all_measurements.extend(measurements)

        if not all_measurements:
            return {"error": f"No measurements found for attribute {attribute}"}

        # Group measurements by type
        grouped_measurements = {}
        for measure in all_measurements:
            measure_type = measure['measure_type']
            if measure_type not in grouped_measurements:
                grouped_measurements[measure_type] = []
            grouped_measurements[measure_type].append(float(measure['value']))

        # Calculate statistics for each measurement type
        stats = {}
        for measure_type, values in grouped_measurements.items():
            try:
                stats[measure_type] = {
                    'count': len(values),
                    'mean': statistics.mean(values),
                    'min': min(values),
                    'max': max(values),
                    'stddev': statistics.stdev(values) if len(values) > 1 else 0
                }
            except (statistics.StatisticsError, ValueError) as e:
                stats[measure_type] = {
                    'error': str(e),
                    'count': len(values)
                }

        return stats