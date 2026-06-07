"""Basic Fluid Movement for P300"""

import pathlib

import plac  # type: ignore [import-untyped]

import tcode_api.api as tc
from tcode_api.cli import (
    DEFAULT_SERVICER_URL,
    output_file_path_annotation,
    servicer_url_annotation,
)
from tcode_api.servicer import TCodeServicerClient
from tcode_api.utilities import (
    create_transform,
    location_as_labware_index,
    mm,
    ul,
    ul_per_s,
)
from script_setup import ScriptIds, setup_script


def append_transfer_commands(
    script: tc.TCodeScript,
    ids: ScriptIds,
    well_index: int,
    trough_index: int,
    transfer_volume_ul: float,
    tip_index: int,
    pipette_volume_ul: int = 300,
    blowout_volume_ul: float = 20,
) -> None:
    """Append pick up tip, aspirate, dispense, and put down tip commands to an existing script.

    Automatically splits into multiple cycles if transfer volume exceeds pipette capacity.

    Args:
        script: The TCodeScript to append commands to.
        ids: ScriptIds from setup_script().
        well_index: Destination well on the plate (0-based, row-major order).
        trough_index: Source well on the trough to aspirate from (0-3).
        transfer_volume_ul: Volume to transfer in microlitres.
        tip_index: Which tip slot to pick up from (0-based, row-major order).
        pipette_volume_ul: Pipette max volume in uL. Default 300.
        blowout_volume_ul: Blowout volume in microlitres. Default 20.
    """
    blowout_volume = ul(blowout_volume_ul)

    # Calculate cycles needed
    usable_volume_ul = pipette_volume_ul - blowout_volume_ul
    if usable_volume_ul <= 0:
        raise ValueError(
            f"blowout_volume_ul ({blowout_volume_ul}) must be less than "
            f"pipette_volume_ul ({pipette_volume_ul})"
        )

    remaining = transfer_volume_ul
    cycle_volumes = []
    while remaining > 0:
        cycle_vol = min(remaining, usable_volume_ul)
        cycle_volumes.append(cycle_vol)
        remaining -= cycle_vol

    # Pick up tip
    script.commands.append(
        tc.PICK_UP_PIPETTE_TIP(
            robot_id=ids.robot_id,
            location=location_as_labware_index(ids.tip_box_id, tip_index, tc.WellPartType.TOP),
        )
    )

    # Transfer cycles
    for i, cycle_vol in enumerate(cycle_volumes):
        cycle_volume = ul(cycle_vol)

        # Aspirate from trough
        script.commands.append(
            tc.MOVE_TO_LOCATION(
                robot_id=ids.robot_id,
                location=location_as_labware_index(
                    ids.trough_id, trough_index, tc.WellPartType.BOTTOM
                ),
            )
        )
        if i == 0:
            script.commands.append(
                tc.ASPIRATE(robot_id=ids.robot_id, volume=blowout_volume, speed=ul_per_s(25))
            )
        script.commands.append(
            tc.ASPIRATE(robot_id=ids.robot_id, volume=cycle_volume, speed=ul_per_s(25))
        )

        # Move to destination well
        script.commands.append(
            tc.MOVE_TO_LOCATION(
                robot_id=ids.robot_id,
                location=tc.LocationRelativeToCurrentPosition(
                    matrix=create_transform(z=mm(150)),
                ),
                path_type=tc.PathType.DIRECT,
            )
        )
        script.commands.append(
            tc.MOVE_TO_LOCATION(
                robot_id=ids.robot_id,
                location=location_as_labware_index(
                    ids.plate_id, well_index, tc.WellPartType.TOP
                ),
                path_type=tc.PathType.DIRECT,
            )
        )

        # Dispense
        script.commands.append(
            tc.DISPENSE(robot_id=ids.robot_id, volume=cycle_volume, speed=ul_per_s(100))
        )

        # Blowout on last cycle
        if i == len(cycle_volumes) - 1:
            script.commands.append(
                tc.DISPENSE(robot_id=ids.robot_id, volume=blowout_volume, speed=ul_per_s(25))
            )

        # Retract after each cycle
        script.commands.append(
            tc.MOVE_TO_LOCATION(
                robot_id=ids.robot_id,
                location=tc.LocationRelativeToCurrentPosition(
                    matrix=create_transform(x=mm(20), y=mm(20), z=mm(20)),
                ),
                path_type=tc.PathType.DIRECT,
            )
        )

    # Put down tip
    script.commands.append(
        tc.PUT_DOWN_PIPETTE_TIP(
            robot_id=ids.robot_id,
            location=location_as_labware_index(ids.tip_box_id, tip_index, tc.WellPartType.TOP),
        )
    )


def fluid_transfer(
    well_index: int,
    trough_index: int,
    transfer_volume_ul: float,
    tip_index: int = 0,
    pipette_volume_ul: int = 300,
    tip_box_deck_slot: int = 2,
    well_plate_name: str = "omen_double_sample_well_plate",
    well_plate_deck_slot: int = 4,
    trough_deck_slot: int = 3,
    blowout_volume_ul: float = 20,
) -> tc.TCodeScript:
    """Build a complete standalone fluid transfer script.

    For single transfers. For multiple transfers, use setup_script() and
    append_transfer_commands() directly to avoid recalibration between transfers.

    Args:
        well_index: Destination well on the plate (0-based, row-major order).
        trough_index: Source well on the trough to aspirate from (0-3).
        transfer_volume_ul: Volume to transfer in microlitres.
        tip_index: Which tip slot to pick up from (0-based, row-major order). Default 0.
        pipette_volume_ul: Pipette max volume in uL; also selects matching tip box. Default 300.
        tip_box_deck_slot: Deck slot number holding the tip box. Default 2.
        well_plate_name: Labware JSON name of the destination well plate.
        well_plate_deck_slot: Deck slot number holding the destination well plate. Default 4.
        trough_deck_slot: Deck slot number holding the trough. Default 3.
        blowout_volume_ul: Blowout volume in microlitres (default 20).
    """
    script = tc.TCodeScript.new(
        name=f"Fluid Transfer to well {well_index} ({transfer_volume_ul}uL)",
    )
    ids = setup_script(
        script,
        pipette_volume_ul=pipette_volume_ul,
        tip_box_deck_slot=tip_box_deck_slot,
        well_plate_name=well_plate_name,
        well_plate_deck_slot=well_plate_deck_slot,
        trough_deck_slot=trough_deck_slot,
    )
    script.commands.append(tc.RETRIEVE_TOOL(robot_id=ids.robot_id, id=ids.pipette_id))
    append_transfer_commands(
        script,
        ids,
        well_index=well_index,
        trough_index=trough_index,
        transfer_volume_ul=transfer_volume_ul,
        tip_index=tip_index,
        pipette_volume_ul=pipette_volume_ul,
        blowout_volume_ul=blowout_volume_ul,
    )
    script.commands.append(tc.RETURN_TOOL(robot_id=ids.robot_id))
    return script
