"""PPM-based dilution script generator."""

import tcode_api.api as tc

from contaminant import Contaminant, ContaminantTarget
from fluid_move import append_transfer_commands
from script_setup import setup_script
from lab_utils import calculate_contaminant_volume


def multi_contaminant_transfer(
    well_index: int,
    diluent_trough_index: int,
    diluent_tip_index: int,
    diluent_volume_ul: float,
    contaminant_targets: list[ContaminantTarget],
    pipette_volume_ul: int = 300,
    tip_box_deck_slot: int = 2,
    well_plate_name: str = "omen_double_sample_well_plate",
    well_plate_deck_slot: int = 4,
    trough_deck_slot: int = 3,
    blowout_volume_ul: float = 20,
) -> tc.TCodeScript:
    """Build a single script for transferring multiple contaminants plus diluent into one well.

    Setup (robot, tools, labware) happens once. All contaminant and diluent transfers
    are appended to the same script, avoiding recalibration between transfers.

    Args:
        well_index: Destination well on the plate (0-based, row-major order).
        diluent_trough_index: Trough well holding the diluent/water (0-3).
        diluent_tip_index: Tip slot to use for the diluent transfer.
        diluent_volume_ul: Volume of diluent to dispense in microlitres.
        contaminant_targets: List of ContaminantTarget defining each contaminant and target ppm.
        pipette_volume_ul: Pipette max volume in uL. Default 300.
        tip_box_deck_slot: Deck slot number holding the tip box. Default 2.
        well_plate_name: Labware JSON name of the destination well plate.
        well_plate_deck_slot: Deck slot number holding the well plate. Default 4.
        trough_deck_slot: Deck slot number holding the trough. Default 3.
        blowout_volume_ul: Blowout volume in microlitres (default 20).

    Returns:
        A single TCodeScript with all transfers in sequence.
    """
    script = tc.TCodeScript.new(
        name=f"Multi Contaminant Transfer to well {well_index}",
    )

    # Setup once — robot, tools, labware resolved a single time
    ids = setup_script(
        script,
        pipette_volume_ul=pipette_volume_ul,
        tip_box_deck_slot=tip_box_deck_slot,
        well_plate_name=well_plate_name,
        well_plate_deck_slot=well_plate_deck_slot,
        trough_deck_slot=trough_deck_slot,
    )

    # Retrieve tool once for all transfers
    script.commands.append(tc.RETRIEVE_TOOL(robot_id=ids.robot_id, id=ids.pipette_id))

    # Append contaminant transfers
    for ct in contaminant_targets:
        contaminant_volume_ul = calculate_contaminant_volume(
            diluent_volume_ul, ct.target_ppm, ct.contaminant.stock_ppm
        )
        print(
            f"  [{ct.contaminant.name}] target={ct.target_ppm}ppm, "
            f"stock={ct.contaminant.stock_ppm}ppm, "
            f"volume={contaminant_volume_ul:.2f}uL"
        )
        append_transfer_commands(
            script,
            ids,
            well_index=well_index,
            trough_index=ct.contaminant.trough_index,
            transfer_volume_ul=contaminant_volume_ul,
            tip_index=ct.contaminant.tip_index,
            pipette_volume_ul=pipette_volume_ul,
            blowout_volume_ul=blowout_volume_ul,
        )

    # Append diluent transfer last
    print(f"  [diluent] volume={diluent_volume_ul:.2f}uL")
    append_transfer_commands(
        script,
        ids,
        well_index=well_index,
        trough_index=diluent_trough_index,
        transfer_volume_ul=diluent_volume_ul,
        tip_index=diluent_tip_index,
        pipette_volume_ul=pipette_volume_ul,
        blowout_volume_ul=blowout_volume_ul,
    )

    # Return tool once after all transfers
    script.commands.append(tc.RETURN_TOOL(robot_id=ids.robot_id))

    return script


def ppm_fluid_transfer(
    well_index: int,
    contaminant_trough_index: int,
    diluent_trough_index: int,
    diluent_volume_ul: float,
    target_ppm: float,
    contaminant_ppm: float,
    contaminant_tip_index: int = 0,
    diluent_tip_index: int = 1,
    pipette_volume_ul: int = 300,
    tip_box_deck_slot: int = 2,
    well_plate_name: str = "omen_double_sample_well_plate",
    well_plate_deck_slot: int = 4,
    blowout_volume_ul: float = 20,
) -> tc.TCodeScript:
    """Build a single script for a single contaminant PPM-based dilution.

    Args:
        well_index: Destination well on the plate (0-based, row-major order).
        contaminant_trough_index: Trough well holding the contaminant (0-3).
        diluent_trough_index: Trough well holding the diluent/water (0-3).
        diluent_volume_ul: Volume of diluent to dispense in microlitres.
        target_ppm: Target concentration in the final sample in ppm (mg/L).
        contaminant_ppm: Concentration of the contaminant stock solution in ppm (mg/L).
        contaminant_tip_index: Tip slot to use for the contaminant transfer. Default 0.
        diluent_tip_index: Tip slot to use for the diluent transfer. Default 1.
        pipette_volume_ul: Pipette max volume in uL. Default 300.
        tip_box_deck_slot: Deck slot number holding the tip box. Default 2.
        well_plate_name: Labware JSON name of the destination well plate.
        well_plate_deck_slot: Deck slot number holding the well plate. Default 4.
        blowout_volume_ul: Blowout volume in microlitres (default 20).

    Returns:
        A single TCodeScript with contaminant and diluent transfers in sequence.
    """
    from contaminant import Contaminant, ContaminantTarget
    contaminant = Contaminant(
        name="contaminant",
        trough_index=contaminant_trough_index,
        tip_index=contaminant_tip_index,
        stock_ppm=contaminant_ppm,
    )
    return multi_contaminant_transfer(
        well_index=well_index,
        diluent_trough_index=diluent_trough_index,
        diluent_tip_index=diluent_tip_index,
        diluent_volume_ul=diluent_volume_ul,
        contaminant_targets=[ContaminantTarget(contaminant=contaminant, target_ppm=target_ppm)],
        pipette_volume_ul=pipette_volume_ul,
        tip_box_deck_slot=tip_box_deck_slot,
        well_plate_name=well_plate_name,
        well_plate_deck_slot=well_plate_deck_slot,
        blowout_volume_ul=blowout_volume_ul,
    )