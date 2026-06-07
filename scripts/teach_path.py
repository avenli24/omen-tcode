"""Teach mode structures for the Synergy HTX plate reader."""

from __future__ import annotations

import datetime
import pathlib

import plac  # type: ignore [import-untyped]
import tcode_api.api as tc
from tcode_api.servicer import TCodeServicerClient
from tcode_api.types import Matrix
from tcode_api.utilities import (
    create_transform,
    describe_well_plate,
    generate_id,
    load_labware,
    mm,
)
from tcode_api.api import ValueWithUnits
import pathlib
from tcode_api.schemas.base import BaseSchemaVersionedModel
import plac  # type: ignore [import-untyped]

DEFAULT_DECK_SLOT = "DeckSlot_1"
DEFAULT_LABWARE = "costar_3603_plate"
DEFAULT_FILE_PATH = (
    pathlib.Path(__file__).resolve().parent.parent / "data" / "path.json"
)
DEFAULT_TCODE_SERVICE_URL = "http://localhost:8002"
DEFAULT_TARGET_PLATE_INDEX = 1

"""Data structure for storing and retrieving multi-point paths."""


import datetime
from typing import Generator, Literal

from tcode_api.types import Matrix


class Path(BaseSchemaVersionedModel):
    """List of transforms representing points in space relative to a robot's base coordinate system."""

    type: Literal["Path"] = "Path"
    timestamp: datetime.datetime
    points: list[Matrix]

    @classmethod
    def new(cls, points: list[Matrix]) -> Path:
        """Create a new Path object with the current timestamp."""
        return cls(timestamp=datetime.datetime.now(), points=points)


def yield_path(
    path: Path, mode: Literal["forward", "backward"] = "forward"
) -> Generator[Matrix, None, None]:
    """Sequentially yield path matrices in the specified direction."""
    if mode == "forward":
        matrix_list = path.points
    elif mode == "backward":
        matrix_list = path.points[::-1]
    else:
        raise ValueError(f"Unrecognized mode {mode}")

    for matrix in matrix_list:
        yield matrix


def _sanitize_deck_slot_name(raw_name: str) -> str:
    """Ensure deck slot name follows 'DeckSlot_#' format."""
    try:
        int_name = int(raw_name)
        return f"DeckSlot_{int_name}"
    except ValueError:
        if raw_name[:9] != "DeckSlot_" or int(raw_name[9:]) < 1:
            raise ValueError(
                "%s not an int, and doesn't contain 'DeckSlot_' => deemed invalid",
                raw_name,
            )
        return raw_name


filepath_annotation = plac.Annotation(
    "Filepath of taught SynergyHTXPath object",
    abbrev="f",
    kind="option",
    type=pathlib.Path,
)
tcode_url_annotation = plac.Annotation(
    "URL of TCodeServicer", kind="option", abbrev="u1", type=str
)

deck_slot_name_annotation = plac.Annotation(
    "Name of deck slot in which to put labware (accepts clean ints) (ex. DeckSlot_1,10)",
    abbrev="d",
    kind="option",
    type=_sanitize_deck_slot_name,
)
labware_name_annotation = plac.Annotation(
    "Name of labware; passed into tc.utilities.load_labware",
    abbrev="l",
    kind="option",
    type=str,
)
serial_number_annotation = plac.Annotation(
    help="Target robot serial number",
    abbrev="r",
    kind="option",
    type=str,
)
gripper_serial_number_annotation = plac.Annotation(
    help="Target gripper serial number",
    abbrev="g",
    kind="option",
    type=str,
)


def _generate_pick_up_labware_script(
    deck_slot_name: str,
    labware_name: str,
    robot_serial_number: str = "",
    pickup_offset_transform: Matrix | None = None,
    robot_id: str | None = None,
    labware_id: str | None = None,
    gripper_id: str | None = None,
    gripper_serial_number: str | None = None,
) -> tuple[tc.TCodeScript, str, str, str]:
    try:
        description = load_labware(labware_name)
    except Exception as err:
        raise ValueError("Invalid labware_name arg %s", labware_name) from err

    script = tc.TCodeScript.new(
        name=__file__,
        description="Teach approach+retract points for path.",
    )
    if robot_id is None:
        robot_descriptor = tc.RobotDescriptor()
        if robot_serial_number != "":
            robot_descriptor.serial_number = robot_serial_number
        robot_id = generate_id()
        script.commands.append(tc.ADD_ROBOT(id=robot_id, descriptor=robot_descriptor))
    if labware_id is None:
        labware_id = generate_id()
        script.commands.append(
            tc.CREATE_LABWARE(
                robot_id=robot_id,
                description=description,
                holder=tc.LabwareHolderName(
                    robot_id=robot_id,
                    name=deck_slot_name,
                ),
            ),
        )
        script.commands.append(
            tc.ADD_LABWARE(id=labware_id, descriptor=describe_well_plate(has_lid=True))
        )
    if gripper_id is None:
        gripper_id = generate_id()
        gripper_descriptor = (
            tc.GripperDescriptor(serial_number=gripper_serial_number)
            if gripper_serial_number
            else tc.GripperDescriptor()
        )
        script.commands.append(
            tc.ADD_TOOL(robot_id=robot_id, id=gripper_id, descriptor=gripper_descriptor)
        )
        script.commands.append(tc.RETRIEVE_TOOL(robot_id=robot_id, id=gripper_id))

    pick_up_labware_command = tc.PICK_UP_LABWARE(
        robot_id=robot_id,
        labware_id=labware_id,
        grasp_type=tc.GraspType.PINCH,
        offset_transform=create_transform(y=mm(0)),
    )
    if pickup_offset_transform is not None:
        pick_up_labware_command.offset_transform = pickup_offset_transform
    script.commands.append(pick_up_labware_command)
    return script, robot_id, gripper_id, labware_id


def _send_gripper_command(
    tc_client: TCodeServicerClient, robot_id: str, state: tc.GripperStateType
) -> None:
    script = tc.TCodeScript.new(name=__file__, description="Gripper command")
    script.commands.append(tc.MOVE_GRIPPER(robot_id=robot_id, gripper_state_type=state))
    tc_client.run_script(script, clean_environment=False)


def teach_path(
    tc_client: TCodeServicerClient, robot_id: str, no_labware: bool = False
) -> Path:
    """Prompt a user to teach a robot a path."""
    if no_labware:
        prompt = "[a(dd point)|o(pen)|c(lose)|d(one)|q(uit)]: "
    else:
        prompt = "[a(dd point)|d(one)|q(uit)]: "
    path = Path(schema_version=1, points=[], timestamp=datetime.datetime.now())
    while True:
        ans = input(prompt).lower()
        print("")
        if ans in ["d", "done"]:
            return path
        if ans in ["q", "quit", "stop", "exit"]:
            raise KeyboardInterrupt("Quit raised in teach_path()")
        if ans in ["a", "add"]:
            point = tc_client.teach_point(robot_id)
            path.points.append(point)
            print(f"Point {len(path.points)} added.")
            continue
        if no_labware and ans in ["o", "open"]:
            _send_gripper_command(tc_client, robot_id, tc.GripperStateType.OPEN)
            continue
        if no_labware and ans in ["c", "close"]:
            _send_gripper_command(tc_client, robot_id, tc.GripperStateType.CLOSE)
            continue
        if ans not in ["y", "yes", ""]:
            print(f"Bad entry {ans}")
        # ans must be yes, go 'round again


@plac.annotations(
    tcode_service_url=tcode_url_annotation,
    no_labware=plac.Annotation("Skip labware pickup", abbrev="nl", kind="flag"),
    deck_slot_name=deck_slot_name_annotation,
    labware_name=labware_name_annotation,
    filepath=filepath_annotation,
    robot_serial_number=serial_number_annotation,
    gripper_serial_number=gripper_serial_number_annotation,
)
def teach(
    tcode_service_url: str = DEFAULT_TCODE_SERVICE_URL,
    no_labware: bool = False,
    deck_slot_name: str = DEFAULT_DECK_SLOT,
    labware_name: str = DEFAULT_LABWARE,
    filepath: pathlib.Path = DEFAULT_FILE_PATH,
    robot_serial_number: str | None = None,
    gripper_serial_number: str | None = None,
) -> None:
    """Teach a given robot a path."""
    script, robot_id, _, __ = _generate_pick_up_labware_script(
        deck_slot_name,
        labware_name,
        robot_serial_number or "",
        gripper_serial_number=gripper_serial_number,
    )

    # Replace PICK_UP_LABWARE with MOVE_GRIPPER
    if no_labware:
        script.commands = script.commands[:-1]
        script.commands.append(
            tc.MOVE_GRIPPER(
                robot_id=robot_id,
                gripper_state_type=tc.GripperStateType.CLOSE,
            )
        )
        script.commands.append(
            tc.WAIT(
                robot_id=robot_id, duration=ValueWithUnits(magnitude=0.5, units="s")
            )
        )
    tc_client = TCodeServicerClient(servicer_url=tcode_service_url)
    tc_client.run_script(script)

    path = teach_path(tc_client, robot_id, no_labware=no_labware)
    with filepath.open("w") as io_obj:
        path.write(io_obj)


@plac.annotations(
    tcode_service_url=tcode_url_annotation,
    deck_slot_name=deck_slot_name_annotation,
    labware_name=labware_name_annotation,
    filepath=filepath_annotation,
    robot_serial_number=serial_number_annotation,
    gripper_serial_number=gripper_serial_number_annotation,
)
def execute_path(
    tcode_service_url: str = DEFAULT_TCODE_SERVICE_URL,
    deck_slot_name: str = DEFAULT_DECK_SLOT,
    labware_name: str = DEFAULT_LABWARE,
    filepath: pathlib.Path = DEFAULT_FILE_PATH,
    robot_serial_number: str | None = None,
    gripper_serial_number: str | None = None,
) -> None:
    """Demonstrate a provided Path."""
    with filepath.open("r") as io_obj:
        path = Path.read(io_obj)
    tc_client = TCodeServicerClient(servicer_url=tcode_service_url)

    # Pick up Labware
    script_1, robot_id, _, __ = _generate_pick_up_labware_script(
        deck_slot_name,
        labware_name,
        robot_serial_number or "",
        gripper_serial_number=gripper_serial_number,
    )
    tc_client.run_script(script_1)

    # Execute Path Forwards
    script_2 = tc.TCodeScript.new(
        name=__file__,
        description="Run loaded Path out --> in",
    )
    # I taught the robot starting at the reader and working backwards, thus
    # Placing the object in the reader is considered "backward". This is probably
    # a confusing system and we need a better way of representing it.
    for matrix in yield_path(path, "backward"):
        script_2.commands.append(
            tc.MOVE_TO_LOCATION(
                robot_id=robot_id,
                location=tc.LocationRelativeToRobot(robot_id=robot_id, matrix=matrix),
                path_type=tc.PathType.DIRECT,
            )
        )
    script_2.commands.append(
        tc.MOVE_GRIPPER(
            robot_id=robot_id,
            gripper_state_type=tc.GripperStateType.OPEN,
        )
    )
    for matrix in yield_path(path, "forward"):
        script_2.commands.append(
            tc.MOVE_TO_LOCATION(
                robot_id=robot_id,
                location=tc.LocationRelativeToRobot(robot_id=robot_id, matrix=matrix),
                path_type=tc.PathType.DIRECT,
            )
        )

    tc_client.run_script(script_2, clean_environment=False)


if __name__ == "__main__":
    plac.call(teach)