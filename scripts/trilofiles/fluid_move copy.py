"""Generate Basic Fluid Movement TCode script for unittesting."""

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
    describe_pipette_tip_box,
    describe_well_plate,
    generate_id,
    load_labware,
    location_as_labware_index,
    mm,
    ul,
    ul_per_s,
)


@plac.annotations(
    servicer_url=servicer_url_annotation, 
    output_file_path=output_file_path_annotation,
)
def main(
    servicer_url: str = DEFAULT_SERVICER_URL,
    output_file_path: pathlib.Path | None = None,
) -> None:
    pipette_volume = ul(300)
    blowout_volume = ul(20)
    transfer_volume = ul(250)
    channel_count = 1
    pipette_descriptor = tc.SingleChannelPipetteDescriptor(max_volume=pipette_volume)
    # trough_bottom_offset = create_transform(z=mm(1))
    # well_bottom_offset = create_transform(z=mm(10))

    script = tc.TCodeScript.new(
        name=f"Fluid Transfer (C1P{pipette_volume.magnitude})",
    )
    (
        robot_id,
        pipette_id,
        plate_id,
        tip_box_id,
        pipette_tip_group_id_1,
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
            description=load_labware("omen_double_sample_well_plate"),
            holder=tc.LabwareHolderName(robot_id=robot_id, name="DeckSlot_4"),
        )
    )
    script.commands.append(
        tc.CREATE_LABWARE(
            robot_id=robot_id,
            description=load_labware("biotix_utip_p300_box"),
            holder=tc.LabwareHolderName(robot_id=robot_id, name="DeckSlot_2"),
        )
    )
    script.commands.append(
        tc.CREATE_LABWARE(
            robot_id=robot_id,
            description=load_labware("mtcbiotech_4_channel_trough"),
            holder=tc.LabwareHolderName(robot_id=robot_id, name="DeckSlot_3"),
        )
    )
    script.commands.append(
        tc.CREATE_LABWARE(
            robot_id=robot_id,
            description=load_labware("3d_printed_trash_can"),
            holder=tc.LabwareHolderName(robot_id=robot_id, name="DeckSlot_1"),
        )
    )

    script.commands.append(
    tc.ADD_LABWARE(
            id=plate_id,
            descriptor=tc.WellPlateDescriptor(
                named_tags={"name": "omen_double_sample_well_plate"}
            ),
    )
)
    script.commands.append(tc.ADD_LABWARE(id=tip_box_id, descriptor=describe_pipette_tip_box()))
    script.commands.append(tc.ADD_LABWARE(id=trash_can_id, descriptor=tc.TrashDescriptor()))
    script.commands.append(
        tc.ADD_LABWARE(
            id=trough_id,
            descriptor=tc.WellPlateDescriptor(),
        )
    )
    script.commands.append(
        tc.ADD_PIPETTE_TIP_GROUP(
            id=pipette_tip_group_id_1,
            descriptor=tc.PipetteTipGroupDescriptor(
                row_count=channel_count,
                column_count=1,
            ),
        )
    )
    #  Actions
    script.commands.append(tc.RETRIEVE_TOOL(robot_id=robot_id, id=pipette_id))
    script.commands.append(
        tc.RETRIEVE_PIPETTE_TIP_GROUP(id=pipette_tip_group_id_1, robot_id=robot_id)
    )

    script.commands.append(
        tc.MOVE_TO_LOCATION(
            robot_id=robot_id,
            location=location_as_labware_index(trough_id, 0, tc.WellPartType.BOTTOM),
        )
    )
    script.commands.append(
        tc.ASPIRATE(robot_id=robot_id, volume=blowout_volume, speed=ul_per_s(25))
    )
    # script.commands.append(
    #     tc.MOVE_TO_LOCATION(
    #         robot_id=robot_id,
    #         location=location_as_labware_index(trough_id, 0, tc.WellPartType.TOP),
    #         path_type=tc.PathType.DIRECT,
    #         location_offset=trough_bottom_offset,
    #     )
    # )
    script.commands.append(
        tc.ASPIRATE(robot_id=robot_id, volume=transfer_volume, speed=ul_per_s(25))
    )

    script.commands.append(
        tc.MOVE_TO_LOCATION(
            robot_id=robot_id,
            location=tc.LocationRelativeToCurrentPosition(
                matrix=create_transform(z=mm(150))  # move 20mm up from current position
                ),
            path_type=tc.PathType.DIRECT,
        )
    )
    script.commands.append(
        tc.MOVE_TO_LOCATION(
            robot_id=robot_id,
            location=location_as_labware_index(plate_id, 1, tc.WellPartType.TOP),
            path_type=tc.PathType.DIRECT,
            #location_offset= well_bottom_offset,
        )
    )
    script.commands.append(
        tc.DISPENSE(robot_id=robot_id, volume=transfer_volume, speed=ul_per_s(100))
    )

    script.commands.append(
        tc.DISPENSE(robot_id=robot_id, volume=blowout_volume, speed=ul_per_s(25))
    )

#     script.commands.append(
#     tc.MOVE_TO_LOCATION(
#         robot_id=robot_id,
#         location=tc.LocationRelativeToCurrentPosition(
#             matrix=create_transform(z=mm(20))  # move 20mm up from current position
#         ),
#         path_type=tc.PathType.DIRECT,
#     )
# )
#     script.commands.append(
#     tc.MOVE_TO_LOCATION(
#         robot_id=robot_id,
#         location=tc.LocationRelativeToCurrentPosition(
#             matrix=create_transform(x=mm(20), y=mm(20))  # move 20 mm right and 20mm in from current position
#         ),
#         path_type=tc.PathType.DIRECT,
#     )
# )
    
    script.commands.append(
    tc.PUT_DOWN_PIPETTE_TIP(
        robot_id=robot_id,
        location=location_as_labware_index(tip_box_id, 0, tc.WellPartType.TOP),
    )
)

   #script.commands.append(tc.RETURN_TOOL(robot_id=robot_id))

    if output_file_path is not None:
        with output_file_path.open("w") as f:
            script.write(f)

    client = TCodeServicerClient(servicer_url=servicer_url)
    client.run_script(script)


if __name__ == "__main__":
    plac.call(main)
