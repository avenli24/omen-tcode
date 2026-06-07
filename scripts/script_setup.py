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
    tip_box_id: str
    pipette_tip_group_id: str
    trash_can_id: str
    trough_id: str


def setup_script(
    script: tc.TCodeScript,
    pipette_volume_ul: int = 300,
    tip_box_deck_slot: int = 2,
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
        pipette_volume_ul: Pipette max volume in uL; also selects matching tip box. Default 300.
        tip_box_deck_slot: Deck slot number holding the tip box. Default 2.
        well_plate_name: Labware JSON name of the destination well plate.
        well_plate_deck_slot: Deck slot number holding the destination well plate. Default 4.
        trough_deck_slot: Deck slot number holding the trough. Default 3.

    Returns:
        ScriptIds containing all IDs needed for subsequent transfer commands.
    """
    pipette_volume = ul(pipette_volume_ul)
    tip_box_name = tip_box_name_for_volume_ul(pipette_volume_ul)
    tip_box_slot = deck_slot(tip_box_deck_slot)
    well_plate_slot = deck_slot(well_plate_deck_slot)
    pipette_descriptor = tc.SingleChannelPipetteDescriptor(max_volume=pipette_volume)

    (
        robot_id,
        pipette_id,
        plate_id,
        tip_box_id,
        pipette_tip_group_id,
        trash_can_id,
        trough_id,
    ) = [generate_id() for _ in range(7)]

    # Resolve robot and pipette
    script.commands.append(tc.ADD_ROBOT(id=robot_id, descriptor=tc.RobotDescriptor()))
    script.commands.append(
        tc.ADD_TOOL(
            robot_id=robot_id,
            id=pipette_id,
            descriptor=pipette_descriptor,
        )
    )

    # Create labware
    script.commands.append(
        tc.CREATE_LABWARE(
            robot_id=robot_id,
            description=load_labware(well_plate_name),
            holder=tc.LabwareHolderName(robot_id=robot_id, name=well_plate_slot),
        )
    )
    script.commands.append(
        tc.CREATE_LABWARE(
            robot_id=robot_id,
            description=load_labware(tip_box_name),
            holder=tc.LabwareHolderName(robot_id=robot_id, name=tip_box_slot),
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

    # Resolve labware
    script.commands.append(
        tc.ADD_LABWARE(
            id=plate_id,
            descriptor=tc.WellPlateDescriptor(
                named_tags={"name": well_plate_name}
            ),
        )
    )
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
        tip_box_id=tip_box_id,
        pipette_tip_group_id=pipette_tip_group_id,
        trash_can_id=trash_can_id,
        trough_id=trough_id,
    )