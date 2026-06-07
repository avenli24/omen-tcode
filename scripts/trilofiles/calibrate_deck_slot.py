"""Generate and run a deck-slot (labware holder) calibration procedure.

This script calibrates a target deck slot using either:
- a probe (probing-based calibration), or
- a pipette (teach-based calibration).

If a pipette is used, a tip box must be created and registered in the deck slot being calibrated.
"""

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
from tcode_api.utilities import describe_pipette_tip_box, generate_id, load_labware, ul

_logger = logging.getLogger(__name__)
_filename = pathlib.Path(__file__).stem


_tool_options: tuple[Literal["pipette", "probe"], ...] = ("pipette", "probe")
_tool_menu = "\n".join([f"{i}. {name}" for i, name in enumerate(("pipette", "probe"), start=1)])


def prompt_probeable_tool_kind() -> Literal["pipette", "probe"]:
    """Prompt user for a kind of tool usable for deck-slot calibration."""
    while True:
        print(_tool_menu)
        print("q. Quit")
        ans = input("Enter the # of your desired tool type: ").lower().strip()
        if ans in ("q", "quit", "exit"):
            print("Exiting...")
            exit(0)
        try:
            index = int(ans) - 1
        except ValueError:
            print(f"Cannot case input to int: '{ans}'")
            continue

        try:
            return _tool_options[index]
        except IndexError:
            print(f"Invalid selection: '{ans}'")
            continue


def prompt_channel_count(choices: Iterable[int]) -> int:
    """Prompt user for channel count of pipette."""
    choice_tuple = tuple(choices)
    while True:
        for option in choice_tuple:
            print(f"{option}. {option}-channel pipette")
        print("q. Quit")
        ans = input("Select channel count: ").lower().strip()
        if ans in ("q", "quit", "exit"):
            print("Exiting...")
            exit(0)
        try:
            channel_count = int(ans)
            if channel_count in choice_tuple:
                return channel_count
            else:
                print(f"Invalid selection. Please choose from {choice_tuple}.")
        except ValueError:
            print(f"Cannot case input to int: '{ans}'")


def prompt_pipette_volume(choices: Iterable[int]) -> tc.ValueWithUnits:
    """Prompt user for pipette max volume."""
    choice_tuple = tuple(choices)
    while True:
        for option in choice_tuple:
            print(f"{option}. {option} uL")
        print("q. Quit")
        ans = input("Select pipette max volume: ").lower().strip()
        if ans in ("q", "quit", "exit"):
            print("Exiting...")
            exit(0)
        try:
            volume = int(ans)
            if volume in choice_tuple:
                return ul(volume)
            else:
                print(f"Invalid selection. Please choose from {choice_tuple}.")
        except ValueError:
            print(f"Cannot case input to int: '{ans}'")


def prompt_deck_slot_name(choices: Iterable[str]) -> str:
    """Prompt user for deck slot name (labware holder name)."""
    choice_list = list(choices)
    while True:
        for i, slot_name in enumerate(choice_list, start=1):
            print(f"{i}. {slot_name}")
        print("q. Quit")
        ans = input("Select deck slot: ").lower().strip()
        if ans in ("q", "quit", "exit"):
            print("Exiting...")
            exit(0)
        try:
            index = int(ans) - 1
        except ValueError:
            print(f"Cannot case input to int: '{ans}'")
            continue

        try:
            return choice_list[index]
        except IndexError:
            print(f"Invalid selection: '{ans}'")
            continue


def normalize_deck_slot_name(deck_slot: str) -> str:
    """Normalize a deck slot identifier to the canonical 'DeckSlot_N' form."""
    raw = deck_slot.strip()
    if raw.isdigit():
        return f"DeckSlot_{int(raw)}"

    lower = raw.lower()
    if lower.startswith("deckslot_"):
        suffix = raw.split("_", 1)[1]
        if suffix.isdigit():
            return f"DeckSlot_{int(suffix)}"
        return f"DeckSlot_{suffix}"

    return raw


def _tip_box_name_for_pipette_max_volume(pipette_max_volume: tc.ValueWithUnits) -> str:
    volume_ul = pipette_max_volume.to("ul").magnitude
    if volume_ul <= 20:
        return "biotix_utip_p20_box"
    if volume_ul <= 300:
        return "biotix_utip_p300_box"
    if volume_ul <= 1000:
        return "biotix_utip_p1000_box"
    raise AssertionError(f"unhandled pipette max volume {pipette_max_volume}")


@plac.annotations(
    servicer_url=servicer_url_annotation,
    output_file_path=output_file_path_annotation,
    deck_slot=plac.Annotation(
        "Deck slot (labware holder) name, e.g. DeckSlot_1. If omitted, prompts interactively.",
        kind="option",
        abbrev="d",
    ),
)
def main(
    servicer_url: str = DEFAULT_SERVICER_URL,
    output_file_path: pathlib.Path | None = None,
    deck_slot: str | None = None,
) -> None:
    """Generate TCode script to calibrate a deck slot using CALIBRATE_LABWARE_HOLDER."""

    tool_kind = prompt_probeable_tool_kind()

    # First select tool details (so pipette channel/volume are asked before deck slot).
    if tool_kind == "probe":
        descriptor: tc.ToolDescriptor = tc.ProbeDescriptor()
        tip_box_name = None
        tool_name_suffix = "Probe"

    elif tool_kind == "pipette":
        pipette_volume = prompt_pipette_volume((20, 300, 1000))
        channel_count = prompt_channel_count((1, 8))

        descriptor_constructor = (
            tc.EightChannelPipetteDescriptor
            if channel_count == 8
            else tc.SingleChannelPipetteDescriptor
        )
        descriptor = descriptor_constructor(max_volume=pipette_volume)
        tip_box_name = _tip_box_name_for_pipette_max_volume(pipette_volume)
        tool_name_suffix = f"C{channel_count}P{pipette_volume.magnitude} Pipette"

    else:
        raise AssertionError(f"unhandled tool kind {tool_kind}")

    # Then select deck slot to calibrate.
    if deck_slot is None:
        deck_slot = prompt_deck_slot_name([f"DeckSlot_{i}" for i in range(1, 17)])
    else:
        deck_slot = normalize_deck_slot_name(deck_slot)

    name = f"Calibrate {deck_slot} ({tool_name_suffix})"

    script = tc.TCodeScript.new(name=name, description=__doc__)

    # FLEET
    robot_id, tool_id, tip_box_id = [generate_id() for _ in range(3)]
    script.commands.append(tc.ADD_ROBOT(id=robot_id, descriptor=tc.RobotDescriptor()))
    script.commands.append(tc.ADD_TOOL(robot_id=robot_id, id=tool_id, descriptor=descriptor))

    # LABWARE (required for pipette teach mode)
    if tip_box_name is not None:
        script.commands.append(
            tc.CREATE_LABWARE(
                robot_id=robot_id,
                description=load_labware(tip_box_name),
                holder=tc.LabwareHolderName(robot_id=robot_id, name=deck_slot),
            )
        )
        script.commands.append(tc.ADD_LABWARE(id=tip_box_id, descriptor=describe_pipette_tip_box()))

    # ACTIONS
    script.commands.append(tc.SWAP_TO_TOOL(robot_id=robot_id, id=tool_id))
    script.commands.append(
        tc.CALIBRATE_LABWARE_HOLDER(
            robot_id=robot_id,
            location=tc.LocationAsLabwareHolder(
                robot_id=robot_id,
                labware_holder_name=deck_slot,
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
