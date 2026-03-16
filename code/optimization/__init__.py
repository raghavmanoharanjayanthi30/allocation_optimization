"""
Optimization architecture package.

This package organizes the assignment pipeline into clear layers:
1) candidate generation
2) scoring
3) optimizer (greedy, Hungarian, flow, MILP)
4) rolling-horizon re-optimization
"""

from .scheduler import Scheduler

__all__ = ["Scheduler"]

