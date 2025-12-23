import sys
import os
sys.path.append(os.getcwd())
from unittest.mock import MagicMock
sys.modules['app.services.analytics'] = MagicMock()
from app.services.strategy_calculator import StrategyCalculator

print("Import successful")
