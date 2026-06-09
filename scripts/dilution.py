"""PPM-based dilution script generator."""

import tcode_api.api as tc

from contaminant import Contaminant, ContaminantTargetPPM
from well_config import WellConfig
from fluid_move import fluid_transfer_commands
from script_setup import setup_script
from lab_utils import calculate_contaminant_volume, select_pipette_volume_ul


def multi_contaminant_transfer(
    well_index: int,
    diluent_trough_index: int,
    diluent_tip_index: int,
    diluent_volume_ul: float,
    contaminant_ppms: list[ContaminantTargetPPM],
    tip_box_slots: dict[int, int] | None = None,
    diluent_tip_box_deck_slot: int = 2,
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
        contaminant_ppms: List of ContaminantTargetPPM defining each contaminant and target ppm.
        tip_box_slots: Dict mapping pipette volume (uL) to deck slot number.
                       e.g. {20: 5, 300: 2, 1000: 6}. Auto-built from contaminants if None.
        diluent_tip_box_deck_slot: Deck slot for the diluent tip box. Default 2.
        well_plate_name: Labware JSON name of the destination well plate.
        well_plate_deck_slot: Deck slot number holding the well plate. Default 4.
        trough_deck_slot: Deck slot number holding the trough. Default 3.
        blowout_volume_ul: Blowout volume in microlitres (default 20).

    Returns:
        A single TCodeScript with all transfers in sequence.
    """
    # Calculate volumes and pipette sizes for all contaminants
    transfers = []
    for ct in contaminant_ppms:
        vol = calculate_contaminant_volume(
            diluent_volume_ul, ct.target_ppm, ct.contaminant.stock_ppm
        )
        pipette_vol = select_pipette_volume_ul(vol)
        transfers.append((ct, vol, pipette_vol))

    diluent_pipette_vol = select_pipette_volume_ul(diluent_volume_ul)

    # Build tip_box_slots automatically if not provided
    if tip_box_slots is None:
        tip_box_slots = {}
        for ct, vol, pipette_vol in transfers:
            if pipette_vol not in tip_box_slots:
                tip_box_slots[pipette_vol] = ct.contaminant.tip_box_deck_slot
        if diluent_pipette_vol not in tip_box_slots:
            tip_box_slots[diluent_pipette_vol] = diluent_tip_box_deck_slot

    # Use the largest pipette volume for the tool descriptor
    max_pipette_vol = max(tip_box_slots.keys())

    script = tc.TCodeScript.new(
        name=f"Multi Contaminant Transfer to well {well_index}",
    )

    # Setup once — robot, tools, labware resolved a single time
    ids = setup_script(
        script,
        pipette_volume_ul=max_pipette_vol,
        tip_box_slots=tip_box_slots,
        well_plate_name=well_plate_name,
        well_plate_deck_slot=well_plate_deck_slot,
        trough_deck_slot=trough_deck_slot,
    )

    # Retrieve tool once for all transfers
    script.commands.append(tc.RETRIEVE_TOOL(robot_id=ids.robot_id, id=ids.pipette_id))

    # Append contaminant transfers
    for ct, contaminant_volume_ul, pipette_vol in transfers:
        print(
            f"  [{ct.contaminant.name}] target={ct.target_ppm}ppm, "
            f"stock={ct.contaminant.stock_ppm}ppm, "
            f"volume={contaminant_volume_ul:.2f}uL, "
            f"pipette={pipette_vol}uL, "
            f"tip_box=DeckSlot_{tip_box_slots[pipette_vol]}"
        )
        fluid_transfer_commands(
            script,
            ids,
            well_index=well_index,
            trough_index=ct.contaminant.trough_index,
            transfer_volume_ul=contaminant_volume_ul,
            tip_index=ct.contaminant.tip_index,
            pipette_volume_ul=pipette_vol,
            blowout_volume_ul=blowout_volume_ul,
        )

    # Append diluent transfer last
    print(
        f"  [diluent] volume={diluent_volume_ul:.2f}uL, "
        f"pipette={diluent_pipette_vol}uL, "
        f"tip_box=DeckSlot_{tip_box_slots[diluent_pipette_vol]}"
    )
    fluid_transfer_commands(
        script,
        ids,
        well_index=well_index,
        trough_index=diluent_trough_index,
        transfer_volume_ul=diluent_volume_ul,
        tip_index=diluent_tip_index,
        pipette_volume_ul=diluent_pipette_vol,
        blowout_volume_ul=blowout_volume_ul,
    )

    # Return tool once after all transfers
    script.commands.append(tc.RETURN_TOOL(robot_id=ids.robot_id))

    return script



def contaminant_fluid_transfer(
    well_index: int,
    contaminant_trough_index: int,
    diluent_trough_index: int,
    diluent_volume_ul: float,
    target_ppm: float,
    contaminant_ppm: float,
    contaminant_tip_index: int = 0,
    diluent_tip_index: int = 1,
    tip_box_slots: dict[int, int] | None = None,
    diluent_tip_box_deck_slot: int = 2,
    well_plate_name: str = "omen_double_sample_well_plate",
    well_plate_deck_slot: int = 4,
    trough_deck_slot: int = 3,
    blowout_volume_ul: float = 20,
) -> tc.TCodeScript:
    """Build a single script for a single contaminant PPM-based dilution."""
    contaminant = Contaminant(
        name="contaminant",
        trough_index=contaminant_trough_index,
        tip_index=contaminant_tip_index,
        stock_ppm=contaminant_ppm,
        tip_box_deck_slot=diluent_tip_box_deck_slot,
    )
    return multi_contaminant_transfer(
        well_index=well_index,
        diluent_trough_index=diluent_trough_index,
        diluent_tip_index=diluent_tip_index,
        diluent_volume_ul=diluent_volume_ul,
        contaminant_ppms=[ContaminantTargetPPM(contaminant=contaminant, target_ppm=target_ppm)],
        tip_box_slots=tip_box_slots,
        diluent_tip_box_deck_slot=diluent_tip_box_deck_slot,
        well_plate_name=well_plate_name,
        well_plate_deck_slot=well_plate_deck_slot,
        trough_deck_slot=trough_deck_slot,
        blowout_volume_ul=blowout_volume_ul,
    )


def multi_sample_creation(
    well_configs: list[WellConfig],
    diluent_trough_index: int,
    diluent_volume_ul: float,
    tip_box_slots: dict[int, int] | None = None,
    diluent_tip_box_deck_slot: int = 2,
    well_plate_name: str = "omen_double_sample_well_plate",
    well_plate_deck_slot: int = 4,
    trough_deck_slot: int = 3,
    blowout_volume_ul: float = 20,
) -> tc.TCodeScript:
    """Build a single script that fills multiple wells each with different contaminants.

    Setup happens once — no recalibration between wells or contaminants.

    Args:
        well_configs: List of WellConfig, one per well, each with its own contaminant targets.
        diluent_trough_index: Trough well holding the diluent/water (0-3).
        diluent_volume_ul: Volume of diluent per well in microlitres.
        tip_box_slots: Dict mapping pipette volume (uL) to deck slot number.
        diluent_tip_box_deck_slot: Deck slot for the diluent tip box. Default 2.
        well_plate_name: Labware JSON name of the destination well plate.
        well_plate_deck_slot: Deck slot number holding the well plate. Default 4.
        trough_deck_slot: Deck slot number holding the trough. Default 3.
        blowout_volume_ul: Blowout volume in microlitres (default 20).

    Returns:
        A single TCodeScript filling all wells in sequence.
    """
    diluent_pipette_vol = select_pipette_volume_ul(diluent_volume_ul)

    # Pre-calculate all volumes across all wells to build tip_box_slots
    if tip_box_slots is None:
        tip_box_slots = {}
        for wc in well_configs:
            for ct in wc.contaminant_ppms:
                vol = calculate_contaminant_volume(
                    diluent_volume_ul, ct.target_ppm, ct.contaminant.stock_ppm
                )
                pipette_vol = select_pipette_volume_ul(vol)
                if pipette_vol not in tip_box_slots:
                    tip_box_slots[pipette_vol] = ct.contaminant.tip_box_deck_slot
        if diluent_pipette_vol not in tip_box_slots:
            tip_box_slots[diluent_pipette_vol] = diluent_tip_box_deck_slot

    max_pipette_vol = max(tip_box_slots.keys())

    script = tc.TCodeScript.new(
        name=f"Custom Multi Well Transfer ({len(well_configs)} wells)",
    )

    # Setup once for all wells
    ids = setup_script(
        script,
        pipette_volume_ul=max_pipette_vol,
        tip_box_slots=tip_box_slots,
        well_plate_name=well_plate_name,
        well_plate_deck_slot=well_plate_deck_slot,
        trough_deck_slot=trough_deck_slot,
    )

    script.commands.append(tc.RETRIEVE_TOOL(robot_id=ids.robot_id, id=ids.pipette_id))

    # Fill each well with its own contaminant mix
    for wc in well_configs:
        print(f"  Well {wc.well_index}:")
        for ct in wc.contaminant_ppms:
            vol = calculate_contaminant_volume(
                diluent_volume_ul, ct.target_ppm, ct.contaminant.stock_ppm
            )
            pipette_vol = select_pipette_volume_ul(vol)
            print(f"    [{ct.contaminant.name}] {vol:.2f}uL ({pipette_vol}uL pipette)")
            fluid_transfer_commands(
                script,
                ids,
                well_index=wc.well_index,
                trough_index=ct.contaminant.trough_index,
                transfer_volume_ul=vol,
                tip_index=ct.contaminant.tip_index,
                pipette_volume_ul=pipette_vol,
                blowout_volume_ul=blowout_volume_ul,
            )
        print(f"    [diluent] {diluent_volume_ul:.2f}uL ({diluent_pipette_vol}uL pipette)")
        fluid_transfer_commands(
            script,
            ids,
            well_index=wc.well_index,
            trough_index=diluent_trough_index,
            transfer_volume_ul=diluent_volume_ul,
            tip_index=wc.diluent_tip_index,
            pipette_volume_ul=diluent_pipette_vol,
            blowout_volume_ul=blowout_volume_ul,
        )

    script.commands.append(tc.RETURN_TOOL(robot_id=ids.robot_id))

    return script