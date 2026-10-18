"""Portfolio Lab V2: guarded comparison of the frozen Portfolio Research strategies.

Isolated from the V1 optimizer: its own configuration (config/v2/), its own data context (the
frozen Research artifacts, development data <= 2023-12-29 only) and its own guard (``guard``).
Entry point for the notebooks: ``open_lab()``.
"""
from .bridge import StrategyLab, load_lab

__all__ = ["StrategyLab", "load_lab", "open_lab"]


def open_lab(**kwargs):
    """Load the frozen strategies (guarded) and return the interactive session used by the notebooks."""
    from .ui import LabSession
    return LabSession.open(**kwargs)
