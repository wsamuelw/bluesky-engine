"""
Shared bot callback wrappers.
"""

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class BotCallbacks:
    """Bundles log, stop_check, and progress callbacks for bot functions."""

    log_callback: Optional[Callable] = None
    stop_check: Optional[Callable] = None
    progress_callback: Optional[Callable] = None

    def log(self, line: str):
        if self.log_callback:
            self.log_callback(line)

    def should_stop(self) -> bool:
        if self.stop_check:
            return self.stop_check()
        return False

    def update_progress(self, completed: int, total: int):
        if self.progress_callback:
            self.progress_callback(completed, total)

    @classmethod
    def from_kwargs(cls, **kwargs):
        """Create from keyword arguments (for backward compatibility)."""
        return cls(
            log_callback=kwargs.get("log_callback"),
            stop_check=kwargs.get("stop_check"),
            progress_callback=kwargs.get("progress_callback"),
        )
