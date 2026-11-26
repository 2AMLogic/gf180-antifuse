"""Physical band boundaries and independent body supplies in array_32x32."""
from dataclasses import dataclass
from pathlib import Path

LAYOUT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Region:
    name: str
    candidate: str
    columns: range
    body: str
    access_length: str

    @property
    def top(self):
        return f"array_region_{self.name.lower()}"

    @property
    def directory(self):
        return LAYOUT / self.top


I = Region("I", "cell_candidate1", range(11), "VSS", "0.70u")
III = Region("III", "cell_candidate3", range(22, 32), "VDDH_III", "0.55u")
