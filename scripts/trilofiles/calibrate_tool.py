"""Run a tool calibration procedure for a probe or pipette (and optionally pipette tip)."""

import logging
import pathlib
from typing import Iterable, Literal

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
    ul,
)

_logger = logging.getLogger(__name__)
_filename = pathlib.Path(__file__).stem


_tool_options: tuple[Literal["pipette", "probe"], ...] = ("pipette", "probe")
_tool_menu = "\n".join([f"{i}. {name}" for i, name in enumerate(("pipette", "probe"), start=1)])


def prompt_probeable_tool_kind() -> Literal["pipette", "probe"]:
    """Prompt user for a kind of tool that can be used for probing.

    Returns:
        EntityKind: The selected tool kind.
    """
    while True:
        print(_tool_menu)
        print("q. Quit")
        ans_a = input("Enter the # of your desired tool type: ").lower()
        if ans_a in ("q", "quit", "exit"):
            print("Exiting...")
            exit(0)
        try:
            index = int(ans_a) - 1
        except ValueError:
            print(f"Cannot case input to int: '{ans_a}'")
            continue

        try:
            return _tool_options[index]
        except IndexError:
            print(f"Invalid selection: '{ans_a}'")
            continue


def prompt_channel_count(choices: Iterable[int]) -> int:
    """Prompt user for channel count of pipette.

    Returns:
        int: The selected channel count (1 or 8).
    """
    while True:
        for option in choices:
            print(f"{option}. {option}-channel pipette")
        print("q. Quit")
        ans = input("Select channel count: ").lower().strip()
        if ans in ("q", "quit", "exit"):
            print("Exiting...")
            exit(0)
        try:
            channel_count = int(ans)
            if channel_count in choices:
                return channel_count
            else:
                print(f"Invalid selection. Please choose from {choices}.")
        except ValueError:
            print(f"Cannot case input to int: '{ans}'")


def prompt_pipette_volume(choices: Iterable[int]) -> tc.ValueWithUnits:
    """Prompt user for pipette volume.

    Returns:
        tc.Volume: The selected pipette volume (20, 300, or 1000 uL).
    """
    while True:
        for option in choices:
            print(f"{option}. {option} uL")
        print("q. Quit")
        ans = input("Select pipette volume: ").lower().strip()
        if ans in ("q", "quit", "exit"):
            print("Exiting...")
            exit(0)
        try:
            volume = int(ans)
            if volume in choices:
                return ul(volume)
            else:
                print(f"Invalid selection. Please choose from {choices}.")
        except ValueError:
            print(f"Cannot case input to int: '{ans}'")


def prompt_pipette_tip_volume(choices: Iterable[int]) -> tc.ValueWithUnits:
    """Prompt user for pipette tip volume.

    Returns:
        tc.Volume: The selected pipette tip volume (20, 300, or 1000 uL).
    """
    while True:
        for option in choices:
            print(f"{option}. {option} uL")
        print("q. Quit")
        ans = input("Select pipette tip volume: ").lower().strip()
        if ans in ("q", "quit", "exit"):
            print("Exiting...")
            exit(0)
        try:
            volume = int(ans)
            if volume in choices:
                return ul(volume)
            else:
                print(f"Invalid selection. Please choose from {choices}.")
        except ValueError:
            print(f"Cannot case input to int: '{ans}'")


def yes_no_prompt(question: str) -> bool:
    """Prompt user with a yes/no question.

    :param question: The question to ask the user.

    :return: True if the user answered yes, False if the user answered no.
    """
    while True:
        ans = input(f"{question} (y/n): ").lower().strip()
        if ans in ("y", "yes"):
            return True
        elif ans in ("n", "no"):
            return False
        else:
            print("Invalid input. Please enter 'y' or 'n'.")


@plac.annotations(
    servicer_url=servicer_url_annotation,
    output_file_path=output_file_path_annotation,
    robot_sn=plac.Annotation(
        "Robot serial number to target (optional).",
        kind="option",
        abbrev="r",
    ),
    z_only=plac.Annotation("If set, only calibrate the Z axis (no XY)", kind="flag", abbrev="z"),
)
def main(
    servicer_url: str = DEFAULT_SERVICER_URL,
    output_file_path: pathlib.Path | None = None,
    robot_sn: str | None = None,
    z_only: bool = False,
) -> None:
    """Generate TCode script to calibrate a tool in z or xy+z. Can calibrate probes, pipette manifolds, or pipette tips."""
    tool_kind = prompt_probeable_tool_kind()
    calibrate_pipette_tip = False
    channel_count: int | None = None
    pipette_tip_volume: tc.ValueWithUnits | None = None
    if tool_kind == "probe":
        name = "Calibrate Probe"
        descriptor: tc.ToolDescriptor = tc.ProbeDescriptor()

    elif tool_kind == "pipette":
        pipette_volume = prompt_pipette_volume((20, 300, 1000))
        channel_count = prompt_channel_count((1, 8))
        calibrate_pipette_tip = yes_no_prompt("Calibrate pipette tip overlap?")
        if calibrate_pipette_tip:
            if pipette_volume == ul(20):
                pipette_tip_volume = ul(20)
            elif pipette_volume == ul(300):
                pipette_tip_volume = prompt_pipette_tip_volume((100, 200, 250, 300))
            elif pipette_volume == ul(1000):
                pipette_tip_volume = ul(1000)
            else:
                raise AssertionError(
                    f"unhandled pipette volume {pipette_volume} for selecting pipette tip volume"
                )

        name = f"Calibrate C{channel_count}P{pipette_volume.magnitude} Pipette"
        if calibrate_pipette_tip:
            name += " Tip"

        descriptor_constructor = (
            tc.EightChannelPipetteDescriptor
            if channel_count == 8
            else tc.SingleChannelPipetteDescriptor
        )
        descriptor = descriptor_constructor(max_volume=pipette_volume)
    else:
        raise AssertionError(f"unhandled tool kind {tool_kind}")

    script = tc.TCodeScript.new(name=name, description=__doc__)

    # FLEET
    (
        robot_id,
        pipette_id,
        tip_box_id,
        pipette_tip_group_id,
    ) = [generate_id() for _ in range(4)]

    robot_descriptor = (
        tc.RobotDescriptor(serial_number=robot_sn) if robot_sn else tc.RobotDescriptor()
    )
    script.commands.append(tc.ADD_ROBOT(id=robot_id, descriptor=robot_descriptor))
    script.commands.append(tc.ADD_TOOL(robot_id=robot_id, id=pipette_id, descriptor=descriptor))

    # LABWARE
    if calibrate_pipette_tip:
        assert pipette_tip_volume is not None
        assert channel_count is not None
        pipette_tip_volume_ul = pipette_tip_volume.to("ul").magnitude
        if pipette_tip_volume_ul <= 20:
            tip_box_name = "biotix_utip_p20_box"
        elif pipette_tip_volume_ul <= 100:
            tip_box_name = "biotix_utip_p100_box"
        elif pipette_tip_volume_ul <= 200:
            tip_box_name = "biotix_utip_p200_box"
        elif pipette_tip_volume_ul <= 250:
            tip_box_name = "biotix_utip_p250_box"
        elif pipette_tip_volume_ul <= 300:
            tip_box_name = "biotix_utip_p300_box"
        elif pipette_tip_volume_ul <= 1000:
            tip_box_name = "biotix_utip_p1000_box"
        else:
            raise AssertionError(f"unhandled pipette tip volume {pipette_tip_volume_ul}")

        script.commands.append(
            tc.CREATE_LABWARE(
                robot_id=robot_id,
                description=load_labware(tip_box_name),
                holder=tc.LabwareHolderName(robot_id=robot_id, name="DeckSlot_8"),
            )
        )
        script.commands.append(tc.ADD_LABWARE(id=tip_box_id, descriptor=describe_pipette_tip_box()))
        script.commands.append(
            tc.ADD_PIPETTE_TIP_GROUP(
                id=pipette_tip_group_id,
                descriptor=tc.PipetteTipGroupDescriptor(
                    row_count=1,
                    column_count=channel_count,
                ),
            )
        )

    # ACTIONS #
    script.commands.append(tc.SWAP_TO_TOOL(robot_id=robot_id, id=pipette_id))
    if calibrate_pipette_tip:
        script.commands.append(
            tc.RETRIEVE_PIPETTE_TIP_GROUP(robot_id=robot_id, id=pipette_tip_group_id)
        )
    script.commands.append(
        tc.CALIBRATE_TOOL(robot_id=robot_id, z_only=z_only, persistent=True),
    )
    if calibrate_pipette_tip:
        script.commands.append(tc.RETURN_PIPETTE_TIP_GROUP(robot_id=robot_id))
    script.commands.append(tc.RETURN_TOOL(robot_id=robot_id))

    if output_file_path is not None:
        with output_file_path.open("w") as f:
            script.write(f)

    client = TCodeServicerClient(servicer_url=servicer_url)
    client.run_script(script)


if __name__ == "__main__":
    plac.call(main)
