import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import plac  # type: ignore [import-untyped]

from tcode_api.cli import (
    DEFAULT_SERVICER_URL,
    output_file_path_annotation,
    servicer_url_annotation,
)
from tcode_api.servicer import TCodeServicerClient

from contaminant import Contaminant, ContaminantTarget
from fluid_move import fluid_transfer
from dilution import multi_contaminant_transfer


copper = Contaminant(name="copper", trough_index=0, tip_index=0, stock_ppm=1000)
zinc   = Contaminant(name="zinc",   trough_index=1, tip_index=1, stock_ppm=500)
iron   = Contaminant(name="iron",   trough_index=2, tip_index=2, stock_ppm=2000)


@plac.annotations(
    servicer_url=servicer_url_annotation,
    output_file_path=output_file_path_annotation,
)
def main(
    servicer_url: str = DEFAULT_SERVICER_URL,
    output_file_path: pathlib.Path | None = None,
) -> None:
    client = TCodeServicerClient(servicer_url=servicer_url)

    # script = fluid_transfer(
    #     well_index=0,
    #     trough_index=0,
    #     transfer_volume_ul=150,
    #     tip_index=0,
    #     pipette_volume_ul=300,
    #     tip_box_deck_slot=2,
    #     well_plate_name="omen_double_sample_well_plate",
    #     well_plate_deck_slot=4,
    # )
    # client.run_script(script)

    # Example 2: multi-contaminant dilution — one script, no recalibration
    print("Well 1:")
    script = multi_contaminant_transfer(
        well_index=1,
        diluent_trough_index=3,
        diluent_tip_index=3,
        diluent_volume_ul=900,
        contaminant_targets=[
            ContaminantTarget(contaminant=copper, target_ppm=10),
            ContaminantTarget(contaminant=zinc,   target_ppm=5),
            ContaminantTarget(contaminant=iron,   target_ppm=2),
        ],
        pipette_volume_ul=300,
        tip_box_deck_slot=2,
        well_plate_name="omen_double_sample_well_plate",
        well_plate_deck_slot=4,
        trough_deck_slot=3,
    )
    client.run_script(script)


if __name__ == "__main__":
    plac.call(main)