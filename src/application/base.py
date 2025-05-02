from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseApplication(ABC):
    """Base class for all applications"""

    def __init__(self):
        self.name = self.__class__.__name__

    @abstractmethod
    def process_data(self, data: Dict) -> Dict:
        """
        Process input data and return results
        Args:
            data: Input data in any format
        Returns:
            Dict: Processed results
        """
        pass