"""Verify a pipette's volumetric accuracy using a 50μl Checkit."""

import logging
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

_logger = logging.getLogger(__name__)


DEFAULT_TRANSFER_VOLUME = ul(50)
DEFAULT_BLOWOUT_VOLUME = ul(10)
DEFAULT_PIPETTE_VOLUME = ul(300)
DEFAULT_CHANNEL_COUNT = 8
DEFAULT_PIPETTE_SPEED = ul_per_s(100)
DEFAULT_WELL_BOTTOM_OFFSET = mm(3)


@plac.annotations(
    servicer_url=servicer_url_annotation,
    output_file_path=output_file_path_annotation,
    transfer_volume=plac.Annotation(
        "volume to transfer in microliters",
        kind="option",
        type=ul,
        abbrev="tv",
    ),
    blowout_volume=plac.Annotation(
        "blowout volume in microliters",
        kind="option",
        type=ul,
        abbrev="bv",
    ),
    pipette_volume=plac.Annotation(
        "pipette max volume in microliters (20, 300, or 1000)",
        kind="option",
        type=ul,
        abbrev="pv",
    ),
    channel_count=plac.Annotation(
        "number of channels on the pipette (1 or 8)",
        kind="option",
        choices=[1, 8],
        abbrev="cc",
    ),
)
def main(
    servicer_url: str = DEFAULT_SERVICER_URL,
    output_file_path: pathlib.Path | None = None,
    transfer_volume: tc.ValueWithUnits = DEFAULT_TRANSFER_VOLUME,
    blowout_volume: tc.ValueWithUnits = DEFAULT_BLOWOUT_VOLUME,
    pipette_volume: tc.ValueWithUnits = DEFAULT_PIPETTE_VOLUME,
    well_bottom_offset: tc.ValueWithUnits = DEFAULT_WELL_BOTTOM_OFFSET,
    channel_count: int = DEFAULT_CHANNEL_COUNT,
) -> None:
    """Generate and execute the `checkit_50ul` TCode script."""
    pipette_volume_ul = pipette_volume.to("ul").magnitude
    if pipette_volume_ul not in (20.0, 300.0, 1000.0):
        raise ValueError("Pipette volume must be 20, 300, or 1000 uL, got %s" % pipette_volume_ul)

    if channel_count not in (1, 8):
        raise ValueError("Channel count must be 1 or 8, got %s" % channel_count)

    _logger.info("Transfer volume: %s", transfer_volume)
    _logger.info("Blowout volume: %s", blowout_volume)
    _logger.info("Pipette volume: %s", pipette_volume)
    _logger.info("Channel count: %s", channel_count)
    script = tc.TCodeScript.new(name=__file__, description=__doc__)

    # FLEET
    (
        robot_id,
        pipette_id,
        plate_id,
        tip_box_id,
        pipette_tip_group_id_1,
        pipette_tip_group_id_2,
        trash_can_id,
    ) = [generate_id() for _ in range(7)]
    script.commands.append(tc.ADD_ROBOT(id=robot_id, descriptor=tc.RobotDescriptor()))
    descriptor_constructor = (
        tc.EightChannelPipetteDescriptor
        if channel_count == 8
        else tc.SingleChannelPipetteDescriptor
    )
    script.commands.append(
        tc.ADD_TOOL(
            robot_id=robot_id,
            id=pipette_id,
            descriptor=descriptor_constructor(max_volume=pipette_volume),
        )
    )
    # LABWARE
    script.commands.append(
        tc.CREATE_LABWARE(
            robot_id=robot_id,
            description=load_labware("checkit_50ul"),
            holder=tc.LabwareHolderName(robot_id=robot_id, name="DeckSlot_16"),
        )
    )
    pipette_volume_ul = pipette_volume.to("ul").magnitude
    if pipette_volume_ul == 20.0:
        tip_box_description = load_labware("biotix_utip_p20_box")
    elif pipette_volume_ul == 300.0:
        tip_box_description = load_labware("biotix_utip_p300_box")
    elif pipette_volume_ul == 1000.0:
        tip_box_description = load_labware("biotix_utip_p1000_box")
    else:
        raise AssertionError("pipette_volume var should already be validated")

    script.commands.append(
        tc.CREATE_LABWARE(
            robot_id=robot_id,
            description=tip_box_description,
            holder=tc.LabwareHolderName(robot_id=robot_id, name="DeckSlot_14"),
        )
    )
    script.commands.append(
        tc.CREATE_LABWARE(
            robot_id=robot_id,
            description=load_labware("3d_printed_trash_can"),
            holder=tc.LabwareHolderName(robot_id=robot_id, name="DeckSlot_13"),
        )
    )
    script.commands.append(tc.ADD_LABWARE(id=plate_id, descriptor=describe_well_plate()))
    script.commands.append(tc.ADD_LABWARE(id=tip_box_id, descriptor=describe_pipette_tip_box()))
    script.commands.append(tc.ADD_LABWARE(id=trash_can_id, descriptor=tc.TrashDescriptor()))
    script.commands.append(
        tc.ADD_PIPETTE_TIP_GROUP(
            id=pipette_tip_group_id_1,
            descriptor=tc.PipetteTipGroupDescriptor(
                row_count=channel_count,
                column_count=1,
            ),
        )
    )

    # ACTIONS #
    script.commands.append(tc.COMMENT(text="50 uL A1 -> A12"))
    well_bottom_offset_matrix = create_transform(z=well_bottom_offset)
    script.commands.append(tc.RETRIEVE_TOOL(robot_id=robot_id, id=pipette_id))
    script.commands.append(
        tc.RETRIEVE_PIPETTE_TIP_GROUP(id=pipette_tip_group_id_1, robot_id=robot_id)
    )
    script.commands.append(
        tc.MOVE_TO_LOCATION(
            robot_id=robot_id,
            location=location_as_labware_index(plate_id, 0, tc.WellPartType.TOP),
        )
    )
    pipette_speed = DEFAULT_PIPETTE_SPEED
    script.commands.append(
        tc.ASPIRATE(robot_id=robot_id, volume=blowout_volume, speed=pipette_speed)
    )
    script.commands.append(
        tc.MOVE_TO_LOCATION(
            robot_id=robot_id,
            location=location_as_labware_index(plate_id, 0, tc.WellPartType.BOTTOM),
            path_type=tc.PathType.DIRECT,
            location_offset=well_bottom_offset_matrix,
        )
    )
    script.commands.append(
        tc.ASPIRATE(robot_id=robot_id, volume=transfer_volume, speed=pipette_speed)
    )
    script.commands.append(
        tc.MOVE_TO_LOCATION(
            robot_id=robot_id,
            location=location_as_labware_index(plate_id, 11, tc.WellPartType.BOTTOM),
            location_offset=well_bottom_offset_matrix,
        )
    )
    script.commands.append(
        tc.DISPENSE(robot_id=robot_id, volume=transfer_volume, speed=pipette_speed)
    )
    script.commands.append(
        tc.MOVE_TO_LOCATION(
            robot_id=robot_id,
            location=location_as_labware_index(plate_id, 11, tc.WellPartType.TOP),
            path_type=tc.PathType.DIRECT,
        )
    )
    script.commands.append(
        tc.DISPENSE(robot_id=robot_id, volume=blowout_volume, speed=pipette_speed)
    )
    script.commands.append(tc.DISCARD_PIPETTE_TIP_GROUP(robot_id=robot_id))
    script.commands.append(tc.RETURN_TOOL(robot_id=robot_id))

    if output_file_path is not None:
        with output_file_path.open("w") as f:
            script.write(f)

    client = TCodeServicerClient(servicer_url=servicer_url)
    client.run_script(script)


if __name__ == "__main__":
    plac.call(main)
