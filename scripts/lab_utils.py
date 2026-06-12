"""Shared laboratory utility functions for TCode scripts."""


def deck_slot(n: int) -> str:
    """Convert a deck slot number to a deck slot name (e.g. 2 -> 'DeckSlot_2')."""
    return f"DeckSlot_{n}"


def tip_box_name_for_volume_ul(volume_ul: int) -> str:
    """Return a Biotix tip-box labware identifier for the given volume (uL)."""
    match int(volume_ul):
        case 20 | 100 | 200 | 250 | 300 | 1000:
            return f"biotix_utip_p{int(volume_ul)}_box"
        case _:
            raise ValueError(
                "Unsupported volume for Biotix uTip box. Expected one of: "
                "20, 100, 200, 250, 300, 1000 (uL). "
                f"Got: {volume_ul}"
            )


def select_pipette_volume_ul(volume_ul: float) -> int:
    """Select the smallest suitable pipette size for a given transfer volume.

    Available sizes: 20, 300, 1000 uL.

    Args:
        volume_ul: Volume to transfer in microlitres.

    Returns:
        Pipette volume in uL (20, 300, or 1000).
    """
    # if volume_ul <= 20:
    #     return 20
    if volume_ul <= 300:
        return 300
    else:
        return 300  # TODO: return 1000 once 1000uL pipette is available
        # return 1000


def calculate_contaminant_volume(
    diluent_volume_ul: float,
    target_ppm: float,
    contaminant_ppm: float,
) -> float:
    """Calculate the volume of contaminant needed to reach a target concentration.

    Uses C1V1 = C2V2 rearranged for a fixed diluent volume:
    contaminant_volume = (target_ppm * diluent_volume) / (contaminant_ppm - target_ppm)

    Args:
        diluent_volume_ul: Volume of diluent in microlitres.
        target_ppm: Target concentration in the final sample in ppm (mg/L).
        contaminant_ppm: Concentration of the contaminant stock solution in ppm (mg/L).

    Returns:
        Volume of contaminant needed in microlitres.
    """
    if contaminant_ppm <= target_ppm:
        raise ValueError(
            f"contaminant_ppm ({contaminant_ppm}) must be greater than target_ppm ({target_ppm})"
        )
    return (target_ppm * diluent_volume_ul) / (contaminant_ppm - target_ppm)


def calculate_total_volume(
    diluent_volume_ul: float,
    target_ppm: float,
    contaminant_ppm: float,
) -> float:
    """Calculate the total sample volume given a fixed diluent volume.

    Args:
        diluent_volume_ul: Volume of diluent in microlitres.
        target_ppm: Target concentration in the final sample in ppm (mg/L).
        contaminant_ppm: Concentration of the contaminant stock solution in ppm (mg/L).

    Returns:
        Total sample volume in microlitres.
    """
    contaminant_volume_ul = calculate_contaminant_volume(
        diluent_volume_ul, target_ppm, contaminant_ppm
    )
    return diluent_volume_ul + contaminant_volume_ul