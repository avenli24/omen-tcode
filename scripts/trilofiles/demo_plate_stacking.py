"""Demonstrate using a labware gripper to stack and un-stack lidded plates."""

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
    robot_id, gripper_id = [generate_id() for _ in range(2)]
    script.commands.append(tc.ADD_ROBOT(id=robot_id, descriptor=tc.RobotDescriptor()))
    script.commands.append(
        tc.ADD_TOOL(robot_id=robot_id, id=gripper_id, descriptor=tc.GripperDescriptor())
    )

    # LABWARE
    plate_count = 3
    script.commands.append(tc.COMMENT(text=f"Create {plate_count} lidded Thermo NUNC plates"))
    labware_ids = [generate_id() for _ in range(plate_count)]
    idxs_in_stack_order = list(range(1, len(labware_ids)))
    labware_holders = [
        tc.LabwareHolderName(robot_id=robot_id, name=f"DeckSlot_{i}") for i in (8, 9, 12)
    ]
    for id, holder in zip(labware_ids, labware_holders):
        script.commands.append(
            tc.CREATE_LABWARE(
                robot_id=robot_id,
                description=load_labware("thermo_nunc_266120_plate"),
                holder=holder,
            ),
        )
        script.commands.append(tc.ADD_LABWARE(id=id, descriptor=describe_well_plate(has_lid=True)))

    # ACTIONS #
    script.commands.append(tc.SWAP_TO_TOOL(robot_id=robot_id, id=gripper_id))

    script.commands.append(tc.COMMENT(text="Stack plates"))
    for idx in idxs_in_stack_order:
        bottom_id, top_id = labware_ids[idx - 1], labware_ids[idx]
        script.commands.append(tc.COMMENT(text=f"Stacking {top_id} on {bottom_id}"))
        script.commands.append(
            tc.PICK_UP_LABWARE(robot_id=robot_id, labware_id=top_id, grasp_type=tc.GraspType.PINCH)
        )
        script.commands.append(
            tc.PUT_DOWN_LABWARE(
                robot_id=robot_id,
                holder=tc.LabwareId(id=bottom_id),
            )
        )

    script.commands.append(tc.COMMENT(text="Move plate stack"))
    deck_slot_name = "DeckSlot_11"
    script.commands.append(tc.COMMENT(text=f"Moving {labware_ids[0]} to {deck_slot_name}"))
    script.commands.append(
        tc.PICK_UP_LABWARE(
            robot_id=robot_id, labware_id=labware_ids[0], grasp_type=tc.GraspType.LIFT
        )
    )
    script.commands.append(
        tc.PUT_DOWN_LABWARE(
            robot_id=robot_id,
            holder=tc.LabwareHolderName(robot_id=robot_id, name=deck_slot_name),
        )
    )

    script.commands.append(tc.COMMENT(text="Un-stack plates"))
    for idx in reversed(idxs_in_stack_order):
        labware_holder = labware_holders[idx]
        labware_id = labware_ids[idx]
        script.commands.append(tc.COMMENT(text=f"Unstacking {labware_id} to {labware_holder.name}"))
        script.commands.append(
            tc.PICK_UP_LABWARE(
                robot_id=robot_id, labware_id=labware_id, grasp_type=tc.GraspType.PINCH
            )
        )
        script.commands.append(
            tc.PUT_DOWN_LABWARE(
                robot_id=robot_id,
                holder=labware_holder,
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
