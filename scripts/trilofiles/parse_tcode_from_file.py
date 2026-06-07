"""CLI tool to validate TCode in a .tc file."""

import pathlib

import plac  # type: ignore [import-untyped]

from tcode_api.api import TCodeScript


@plac.annotations(
    file_path=plac.Annotation(".tc file to parse", type=pathlib.Path),
)
def main(file_path: pathlib.Path) -> None:
    """Load and validate a .tc file."""
    with file_path.open() as io_object:
        file_text = io_object.read()

    TCodeScript.model_validate_json(file_text)


if __name__ == "__main__":
    plac.call(main)
