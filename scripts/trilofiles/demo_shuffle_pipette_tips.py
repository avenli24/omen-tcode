"""Move Pipette tips between tip boxes on the robot's deck."""

import logging
import random
from typing import Literal

import plac  # type: ignore [import-untyped]

import tcode_api.api as tc
from tcode_api.cli import (
    DEFAULT_SERVICER_URL,
    output_file_path_annotation,
    servicer_url_annotation,
)
from tcode_api.servicer import TCodeServicerClient
from tcode_api.utilities import (
    describe_pipette_tip_box,
    generate_id,
    load_labware,
    location_as_labware_index,
)

_logger = logging.getLogger(__name__)


def str_list_from_csv(input: str) -> list[str]:
    """Convert a comma-separated string to a list of strings."""
    return [item.strip() for item in input.split(",")]


@plac.annotations(
    deck_slots_with_full_boxes=plac.Annotation(
        "csv deck slot numbers holding full tip boxes (ex. '1,12,N')",
        type=str_list_from_csv,
    ),
    deck_slots_with_empty_boxes=plac.Annotation(
        "csv deck slot numbers holding empty tip boxes (ex. '2,3,E')",
        type=str_list_from_csv,
    ),
    pipette=plac.Annotation(
        "Pipette type to use ('c1' for single-channel, 'c8' for 8-channel)",
        choices=("c1", "c8"),
    ),
    servicer_url=servicer_url_annotation,
    output_file_path=output_file_path_annotation,
)
def main(
    deck_slots_with_full_boxes: list[str],
    deck_slots_with_empty_boxes: list[str],
    pipette: Literal["c1", "c8"],
    servicer_url: str = DEFAULT_SERVICER_URL,
    output_file_path: str | None = None,
) -> None:
    random.seed(0)  # Standardize the generated ids
    robot_id, tool_id = [generate_id() for _ in range(2)]
    volume = tc.ValueWithUnits(units="ul", magnitude=300)

    # Generate labware ids and pipette descriptors
    match pipette:
        case "c1":
            labware_indices = list(range(96))  # All wells
            descriptor: tc.PipetteDescriptor = tc.SingleChannelPipetteDescriptor(max_volume=volume)
        case "c8":
            labware_indices = list(range(12))  # Only columns
            descriptor = tc.EightChannelPipetteDescriptor(max_volume=volume)
        case _:
            raise ValueError(f"Invalid pipette type: {pipette}")

    # ROBOT
    script = tc.TCodeScript.new(name=__file__, description=__doc__)
    script.commands.append(tc.ADD_ROBOT(id=robot_id, descriptor=tc.RobotDescriptor()))
    script.commands.append(tc.ADD_TOOL(robot_id=robot_id, id=tool_id, descriptor=descriptor))

    # LABWARE
    full_labware_ids, empty_labware_ids = [], []
    for i, deck_slot_number in enumerate(deck_slots_with_full_boxes):
        full_labware_ids.append(generate_id())
        script.commands.append(
            tc.CREATE_LABWARE(
                robot_id=robot_id,
                description=load_labware("biotix_utip_300ul"),
                holder=tc.LabwareHolderName(robot_id=robot_id, name=f"DeckSlot_{deck_slot_number}"),
            )
        )
        script.commands.append(
            tc.ADD_LABWARE(id=full_labware_ids[-1], descriptor=describe_pipette_tip_box())
        )

    # Make custom description for empty tip box
    empty_pipette_tip_box_description = load_labware("biotix_utip_300ul")
    assert isinstance(empty_pipette_tip_box_description, tc.PipetteTipBoxDescription)
    empty_pipette_tip_box_description.pipette_tip_layout = tc.PipetteTipLayout.empty()

    for i, deck_slot_number in enumerate(deck_slots_with_empty_boxes):
        empty_labware_ids.append(generate_id())
        script.commands.append(
            tc.CREATE_LABWARE(
                robot_id=robot_id,
                description=empty_pipette_tip_box_description,
                holder=tc.LabwareHolderName(robot_id=robot_id, name=f"DeckSlot_{deck_slot_number}"),
            )
        )
        script.commands.append(
            tc.ADD_LABWARE(
                id=empty_labware_ids[-1],
                descriptor=describe_pipette_tip_box(pipette_tip_layout=tc.PipetteTipLayout.empty()),
            )
        )

    # ACTIONS #
    script.commands.append(tc.RETRIEVE_TOOL(robot_id=robot_id, id=tool_id))
    for i in range(1):
        source_plate_id = random.choice(full_labware_ids)
        destination_plate_id = random.choice(empty_labware_ids)

        for labware_index in labware_indices:
            script.commands.append(
                tc.PICK_UP_PIPETTE_TIP(
                    robot_id=robot_id,
                    location=location_as_labware_index(source_plate_id, labware_index),
                )
            )
            script.commands.append(
                tc.PUT_DOWN_PIPETTE_TIP(
                    robot_id=robot_id,
                    location=location_as_labware_index(destination_plate_id, labware_index),
                )
            )

        # Update full - empty state tracking
        empty_labware_ids.append(source_plate_id)
        empty_labware_ids.remove(destination_plate_id)
        full_labware_ids.remove(source_plate_id)
        full_labware_ids.append(destination_plate_id)

    script.commands.append(tc.RETURN_TOOL(robot_id=robot_id))

    if output_file_path is not None:
        with open(output_file_path, "w") as f:
            script.write(f)

    client = TCodeServicerClient(servicer_url=servicer_url)
    client.run_script(script)


if __name__ == "__main__":
    plac.call(main)
