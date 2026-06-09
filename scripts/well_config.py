"""WellConfig dataclass for defining per-well contaminant configurations."""

from dataclasses import dataclass

from contaminant import ContaminantTargetPPM


@dataclass
class WellConfig:
    """Configuration for a single well — which well and what contaminants to add.

    Attributes:
        well_index: Destination well on the plate (0-based, row-major order).
        contaminant_ppms: List of ContaminantTargetPPM for this well.
        diluent_tip_index: Tip slot to use for the diluent in this well.
    """
    well_index: int
    contaminant_ppms: list[ContaminantTargetPPM]
    diluent_tip_index: int