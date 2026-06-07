"""Demonstrate using a labware gripper to move a plate by lifting and pinching."""

import pathlib

import plac  # type: ignore [import-untyped]

import tcode_api.api as tc
from tcode_api.cli import (
    DEFAULT_SERVICER_URL,
    output_file_path_annotation,
    servicer_url_annotation,
)
from tcode_api.servicer import TCodeServicerClient
from tcode_api.utilities import describe_well_plate, generate_id, load_labware


@plac.annotations(
    servicer_url=servicer_url_annotation,
    output_file_path=output_file_path_annotation,
)
def main(
    servicer_url: str = DEFAULT_SERVICER_URL,
    output_file_path: pathlib.Path | None = None,
) -> None:
    script = tc.TCodeScript.new(
        name=__file__,
        description=__doc__,
    )

    # FLEET
    robot_id, gripper_id, labware_id = [generate_id() for _ in range(3)]
    script.commands.append(tc.ADD_ROBOT(id=robot_id, descriptor=tc.RobotDescriptor()))
    script.commands.append(
        tc.ADD_TOOL(robot_id=robot_id, id=gripper_id, descriptor=tc.GripperDescriptor())
    )

    # LABWARE
    script.commands.append(
        tc.CREATE_LABWARE(
            robot_id=robot_id,
            description=load_labware("costar_3603_plate"),
            holder=tc.LabwareHolderName(
                robot_id=robot_id,
                name="DeckSlot_1",
            ),
        ),
    )
    script.commands.append(
        tc.ADD_LABWARE(id=labware_id, descriptor=describe_well_plate(has_lid=True))
    )

    # ACTIONS #
    script.commands.append(tc.SWAP_TO_TOOL(robot_id=robot_id, id=gripper_id))
    script.commands.append(tc.COMMENT(text="Move labware with lift"))
    script.commands.append(tc.PICK_UP_LABWARE(robot_id=robot_id, labware_id=labware_id))
    script.commands.append(
        tc.PUT_DOWN_LABWARE(
            robot_id=robot_id,
            holder=tc.LabwareHolderName(
                robot_id=robot_id,
                name="DeckSlot_2",
            ),
        )
    )
    script.commands.append(tc.COMMENT(text="Move labware with pinch"))
    script.commands.append(
        tc.PICK_UP_LABWARE(robot_id=robot_id, labware_id=labware_id, grasp_type=tc.GraspType.PINCH)
    )
    script.commands.append(
        tc.PUT_DOWN_LABWARE(
            robot_id=robot_id,
            holder=tc.LabwareHolderName(
                robot_id=robot_id,
                name="DeckSlot_1",
            ),
        )
    )
    script.commands.append(tc.RETURN_TOOL(robot_id=robot_id))

    if output_file_path is not None:
        with output_file_path.open("w") as f:
            script.write(f)

    client = TCodeServicerClient(servicer_url=servicer_url)
    client.run_script(script)


if __name__ == "__main__":
    plac.call(main)
