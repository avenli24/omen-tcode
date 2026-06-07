"""Pick up pipette tips (via tip-group) from a tip box in a given deck slot.

This script creates a Biotix tip box in the requested deck slot, mounts a pipette, and
retrieves+returns a resolved pipette tip group.

Required arguments:
  pipette     Pipette type: 'c1' (single-channel) or 'c8' (8-channel)
  deck_slot   Deck slot holding the tip box (e.g. -d 8 or -d DeckSlot_8)

Tip selection:
  - Single-channel (c1): use -w with a well or comma-separated wells (e.g. -w A1 or -w A1,B2,H12)
  - 8-channel (c8): use -c with a column or comma-separated columns (e.g. -c 1 or -c 1,3,12)
"""

import logging
import pathlib
import re
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
    describe_pipette_tip_group,
    generate_id,
    load_labware,
    ul,
)

_logger = logging.getLogger(__name__)


def normalize_deck_slot_name(deck_slot: str) -> str:
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


_well_re = re.compile(r"^([A-Ha-h])\s*(\d{1,2})$")


def parse_well_96(well: str) -> int:
    """Parse a well like A1 into a 0-based index for an 8x12 grid (row-major)."""
    m = _well_re.match(well.strip())
    if m is None:
        raise ValueError(f"Invalid well: {well!r} (expected like A1)")

    row_letter = m.group(1).upper()
    col = int(m.group(2))
    if not (1 <= col <= 12):
        raise ValueError(f"Invalid column in well {well!r}: {col} (expected 1-12)")

    row = ord(row_letter) - ord("A")
    if not (0 <= row <= 7):
        raise ValueError(f"Invalid row in well {well!r}: {row_letter} (expected A-H)")

    return row * 12 + (col - 1)


def split_csv(value: str) -> list[str]:
    """Split a comma-separated string into stripped tokens (dropping empties)."""
    return [token.strip() for token in value.split(",") if token.strip()]


def tip_box_name_for_volume_ul(volume_ul: int) -> str:
    """Return a Biotix tip-box labware identifier for the given volume (uL)."""
    match int(volume_ul):
        case 20 | 100 | 200 | 250 | 300 | 1000:
            return f"biotix_utip_p{int(volume_ul)}_box"
        case _:
            raise ValueError(
                "Unsupported volume for Biotix uTip box. Expected one of: "
                "20, 100, 200, 250, 300, 1000 (uL). "
                f"Got: {volume_ul}"
            )


def manifold_match_tag_for_volume_ul(volume_ul: int) -> str:
    match int(volume_ul):
        case 20:
            return "manifold_match_5"
        case 100:
            return "manifold_match_9"
        case 200:
            return "manifold_match_8"
        case 250:
            return "manifold_match_7"
        case 300:
            return "manifold_match_1"
        case 1000:
            return "manifold_match_6"
        case _:
            raise ValueError(f"Unsupported volume for manifold match tag: {volume_ul}")


@plac.annotations(
    pipette=plac.Annotation(
        "Pipette type to use ('c1' for single-channel, 'c8' for 8-channel)",
        choices=("c1", "c8"),
    ),
    volume_ul=plac.Annotation(
        "Pipette max volume in uL; also selects matching Biotix tip box JSON",
        kind="option",
        abbrev="v",
        type=int,
    ),
    deck_slot=plac.Annotation(
        "Deck slot holding the tip box (e.g. '8' or 'DeckSlot_8')",
    ),
    well=plac.Annotation(
        "Single-channel only: well or comma-separated wells (e.g. A1 or A1,B2,H12)",
        kind="option",
        abbrev="w",
    ),
    column=plac.Annotation(
        "8-channel only: target column number (1-12) or comma-separated list (ex. '1,12')",
        kind="option",
        abbrev="c",
        type=str,
    ),
    keep_tool=plac.Annotation(
        "Keep the tool mounted at the end (skip RETURN_TOOL)",
        kind="flag",
        abbrev="k",
    ),
    servicer_url=servicer_url_annotation,
    output_file_path=output_file_path_annotation,
)
def main(
    pipette: Literal["c1", "c8"],
    deck_slot: str,
    volume_ul: int = 300,
    well: str | None = None,
    column: str | None = None,
    keep_tool: bool = False,
    servicer_url: str = DEFAULT_SERVICER_URL,
    output_file_path: pathlib.Path | None = None,
) -> None:
    """Generate and run a minimal script to pick up one tip."""

    deck_slot_name = normalize_deck_slot_name(deck_slot)
    pipette_volume = ul(volume_ul)
    tip_box_name = tip_box_name_for_volume_ul(volume_ul)
    manifold_match_tag = manifold_match_tag_for_volume_ul(volume_ul)
    tip_model = f"biotix_utip_p{int(volume_ul)}.obj"

    if pipette == "c1":
        if well is None:
            raise ValueError("Missing --well (ex. -w A1 or -w A1,B2) for single-channel pipette")
        wells = split_csv(well)
        if len(wells) == 0:
            raise ValueError("No wells provided")
        tip_indices = [parse_well_96(w) for w in wells]
        descriptor: tc.PipetteDescriptor = tc.SingleChannelPipetteDescriptor(
            max_volume=pipette_volume
        )
        script_name = f"Pick up tips {deck_slot_name} ({','.join(w.upper() for w in wells)}) (C1)"
        tip_group_rows, tip_group_cols = 1, 1
        tip_group_count = 96

    elif pipette == "c8":
        if column is None:
            raise ValueError("Missing --column (ex. -c 1 or -c '1,3,12') for 8-channel pipette")
        column_tokens = split_csv(str(column))
        if len(column_tokens) == 0:
            raise ValueError("No columns provided")
        try:
            column_values = [int(tok) for tok in column_tokens]
        except ValueError as e:
            raise ValueError(f"Invalid --column value: {column!r}") from e

        for col in column_values:
            if not (1 <= int(col) <= 12):
                raise ValueError(f"Invalid column {col!r} (expected 1-12)")
        tip_indices = [int(col) - 1 for col in column_values]
        descriptor = tc.EightChannelPipetteDescriptor(max_volume=pipette_volume)
        script_name = (
            f"Pick up tips {deck_slot_name} (Cols{','.join(str(c) for c in column_values)}) (C8)"
        )
        tip_group_rows, tip_group_cols = 8, 1
        tip_group_count = 12

    else:
        raise AssertionError(f"Unhandled pipette type {pipette!r}")

    # IDs
    robot_id, tool_id, tip_box_id = [generate_id() for _ in range(3)]

    script = tc.TCodeScript.new(name=script_name, description=__doc__)

    # ROBOT + TOOL
    script.commands.append(tc.ADD_ROBOT(id=robot_id, descriptor=tc.RobotDescriptor()))
    script.commands.append(tc.ADD_TOOL(robot_id=robot_id, id=tool_id, descriptor=descriptor))

    # TIP BOX LABWARE
    # Add a unique tag to the tips created by this script so tip-group resolution
    # won't accidentally match tips from other racks already on the deck.
    unique_tip_tag = f"script_tip_tag_{generate_id()}"
    tip_box_description = load_labware(tip_box_name)
    assert isinstance(tip_box_description, tc.PipetteTipBoxDescription)
    if unique_tip_tag not in tip_box_description.pipette_tip.tags:
        tip_box_description.pipette_tip.tags.append(unique_tip_tag)

    script.commands.append(
        tc.CREATE_LABWARE(
            robot_id=robot_id,
            description=tip_box_description,
            holder=tc.LabwareHolderName(robot_id=robot_id, name=deck_slot_name),
        )
    )
    script.commands.append(
        tc.ADD_LABWARE(
            id=tip_box_id,
            descriptor=describe_pipette_tip_box(named_tags={"name": tip_box_name}),
        )
    )

    # TIP GROUP RESOLUTION
    # Create an indexable list of tip-group ids (96 wells for c1, 12 columns for c8)
    # so we can retrieve+return the exact requested locations.
    tip_group_descriptor = describe_pipette_tip_group(
        row_count=tip_group_rows,
        column_count=tip_group_cols,
        tags=[manifold_match_tag, unique_tip_tag],
        named_tags={
            "brand": "biotix_utip",
            "model": tip_model,
            "max_volume": float(int(volume_ul)),
        },
    )
    tip_group_ids: list[str] = []
    for _ in range(int(tip_group_count)):
        tip_group_id = generate_id()
        tip_group_ids.append(tip_group_id)
        script.commands.append(
            tc.ADD_PIPETTE_TIP_GROUP(id=tip_group_id, descriptor=tip_group_descriptor)
        )

    # ACTIONS
    script.commands.append(tc.RETRIEVE_TOOL(robot_id=robot_id, id=tool_id))
    for idx in tip_indices:
        if not (0 <= int(idx) < len(tip_group_ids)):
            raise ValueError(f"Tip index out of range: {idx}")
        script.commands.append(
            tc.RETRIEVE_PIPETTE_TIP_GROUP(robot_id=robot_id, id=tip_group_ids[int(idx)])
        )
        script.commands.append(tc.RETURN_PIPETTE_TIP_GROUP(robot_id=robot_id))
    if not keep_tool:
        script.commands.append(tc.RETURN_TOOL(robot_id=robot_id))

    if output_file_path is not None:
        with output_file_path.open("w") as f:
            script.write(f)

    client = TCodeServicerClient(servicer_url=servicer_url)
    client.run_script(script)


if __name__ == "__main__":
    plac.call(main)
