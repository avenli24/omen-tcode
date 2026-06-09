"""Script setup utilities for TCode scripts."""

from dataclasses import dataclass

import tcode_api.api as tc
from tcode_api.schemas.pipette_tip_layout import PipetteTipLayout
from tcode_api.utilities import (
    generate_id,
    load_labware,
    ul,
)
from lab_utils import deck_slot, tip_box_name_for_volume_ul


@dataclass
class ScriptIds:
    """IDs assigned during script setup, used to reference labware in transfer commands."""
    robot_id: str
    pipette_id: str
    plate_id: str
    tip_box_ids: dict[int, str]  # maps pipette_volume_ul -> tip_box_id
    pipette_tip_group_id: str
    trash_can_id: str
    trough_id: str


def setup_script(
    script: tc.TCodeScript,
    pipette_volume_ul: int = 300,
    tip_box_slots: dict[int, int] | None = None,
    well_plate_name: str = "omen_double_sample_well_plate",
    well_plate_deck_slot: int = 4,
    trough_deck_slot: int = 3,
) -> ScriptIds:
    """Add robot, tool, and labware setup commands to an existing script.

    Call this once at the start of a script to resolve the robot, pipette,
    and all labware. Use the returned ScriptIds to reference them in subsequent
    transfer commands.

    Args:
        script: The TCodeScript to append setup commands to.
        pipette_volume_ul: Max pipette volume in uL for the tool descriptor. Default 300.
        tip_box_slots: Dict mapping pipette volume (uL) to deck slot number.
                       e.g. {20: 5, 300: 2, 1000: 6}. Defaults to {pipette_volume_ul: 2}.
        well_plate_name: Labware JSON name of the destination well plate.
        well_plate_deck_slot: Deck slot number holding the destination well plate. Default 4.
        trough_deck_slot: Deck slot number holding the trough. Default 3.

    Returns:
        ScriptIds containing all IDs needed for subsequent transfer commands.
    """
    if tip_box_slots is None:
        tip_box_slots = {pipette_volume_ul: 2}

    pipette_volume = ul(pipette_volume_ul)
    well_plate_slot = deck_slot(well_plate_deck_slot)
    pipette_descriptor = tc.SingleChannelPipetteDescriptor(max_volume=pipette_volume)

    (
        robot_id,
        pipette_id,
        plate_id,
        pipette_tip_group_id,
        trash_can_id,
        trough_id,
    ) = [generate_id() for _ in range(6)]

    # Generate a unique id per tip box
    tip_box_ids = {vol: generate_id() for vol in tip_box_slots}

    # Resolve robot and pipette
    script.commands.append(tc.ADD_ROBOT(id=robot_id, descriptor=tc.RobotDescriptor()))
    script.commands.append(
        tc.ADD_TOOL(
            robot_id=robot_id,
            id=pipette_id,
            descriptor=pipette_descriptor,
        )
    )

    # Create well plate labware
    script.commands.append(
        tc.CREATE_LABWARE(
            robot_id=robot_id,
            description=load_labware(well_plate_name),
            holder=tc.LabwareHolderName(robot_id=robot_id, name=well_plate_slot),
        )
    )

    # Create a tip box for each pipette size
    for vol, slot in tip_box_slots.items():
        tip_box_name = tip_box_name_for_volume_ul(vol)
        script.commands.append(
            tc.CREATE_LABWARE(
                robot_id=robot_id,
                description=load_labware(tip_box_name),
                holder=tc.LabwareHolderName(robot_id=robot_id, name=deck_slot(slot)),
            )
        )

    script.commands.append(
        tc.CREATE_LABWARE(
            robot_id=robot_id,
            description=load_labware("mtcbiotech_4_channel_trough"),
            holder=tc.LabwareHolderName(robot_id=robot_id, name=deck_slot(trough_deck_slot)),
        )
    )
    script.commands.append(
        tc.CREATE_LABWARE(
            robot_id=robot_id,
            description=load_labware("3d_printed_trash_can"),
            holder=tc.LabwareHolderName(robot_id=robot_id, name="DeckSlot_1"),
        )
    )

    # Resolve well plate labware
    script.commands.append(
        tc.ADD_LABWARE(
            id=plate_id,
            descriptor=tc.WellPlateDescriptor(
                named_tags={"name": well_plate_name}
            ),
        )
    )

    # Resolve each tip box
    for vol, tip_box_id in tip_box_ids.items():
        tip_box_name = tip_box_name_for_volume_ul(vol)
        script.commands.append(
            tc.ADD_LABWARE(
                id=tip_box_id,
                descriptor=tc.PipetteTipBoxDescriptor(
                    named_tags={"name": tip_box_name},
                    pipette_tip_layout=PipetteTipLayout.full(row_count=8, column_count=12),
                ),
            )
        )

    script.commands.append(tc.ADD_LABWARE(id=trash_can_id, descriptor=tc.TrashDescriptor()))
    script.commands.append(
        tc.ADD_LABWARE(
            id=trough_id,
            descriptor=tc.WellPlateDescriptor(),
        )
    )
    script.commands.append(
        tc.ADD_PIPETTE_TIP_GROUP(
            robot_id=robot_id,
            id=pipette_tip_group_id,
            descriptor=tc.PipetteTipGroupDescriptor(
                row_count=1,
                column_count=1,
            ),
        )
    )

    return ScriptIds(
        robot_id=robot_id,
        pipette_id=pipette_id,
        plate_id=plate_id,
        tip_box_ids=tip_box_ids,
        pipette_tip_group_id=pipette_tip_group_id,
        trash_can_id=trash_can_id,
        trough_id=trough_id,
    )