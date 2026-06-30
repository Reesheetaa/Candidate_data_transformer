"""Abstract base class for all source adapters.

An adapter's only job is to read raw input and convert it into one or more
PartialCandidate objects. Adapters never normalize, merge, or resolve conflicts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.models import PartialCandidate


class BaseAdapter(ABC):
    source_name: str = "unknown"

    @abstractmethod
    def parse(self, path: str) -> list[PartialCandidate]:
        """Parse the input at `path` into one or more PartialCandidate objects.

        Returns an empty list if the file is missing, empty, or unreadable —
        adapters must never raise on bad input.
        """
        raise NotImplementedError
