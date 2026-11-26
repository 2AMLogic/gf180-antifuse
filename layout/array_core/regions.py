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
    pitch: tuple = (12, 9)
    word_y: float = 1.8
    body_y: float = 6.
    spine_x: float = -3.

    @property
    def top(self):
        return f"array_region_{self.name.lower()}"

    @property
    def directory(self):
        return LAYOUT / self.top


I = Region("I", "cell_candidate1", range(11), "VSS", "0.70u")
II = Region("II", "cell_candidate2", range(11, 22), "VSS", "0.60u",
            pitch=(28, 32), word_y=5.0, body_y=7.5, spine_x=-4.)
III = Region("III", "cell_candidate3", range(22, 32), "VDDH_III", "0.55u")
