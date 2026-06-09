"""Contaminant dataclass for defining stock solutions."""

from dataclasses import dataclass


@dataclass
class Contaminant:
    """Represents a contaminant stock solution.

    Attributes:
        name: Human-readable name of the contaminant (e.g. 'lead').
        trough_index: Trough well index holding the stock solution (0-3).
        tip_index: Tip slot index to use when pipetting this contaminant (0-based, row-major).
        stock_ppm: Concentration of the stock solution in ppm (mg/L).
        tip_box_deck_slot: Deck slot number holding the tip box for this contaminant. Default 2.
    """
    name: str
    trough_index: int
    tip_index: int
    stock_ppm: float
    tip_box_deck_slot: int = 2


@dataclass
class ContaminantTargetPPM:
    """Pairs a contaminant with a target concentration for a specific sample.

    Attributes:
        contaminant: The contaminant stock solution to use.
        target_ppm: Desired concentration in the final sample in ppm (mg/L).
    """
    contaminant: Contaminant
    target_ppm: float