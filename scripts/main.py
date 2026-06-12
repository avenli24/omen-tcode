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

from contaminant import Contaminant, ContaminantTargetPPM
from well_config import WellConfig
from dilution import multi_sample_creation


# Define contaminant stock solutions
copper = Contaminant(name="copper", trough_index=0, tip_index=0, stock_ppm=1000, tip_box_deck_slot=2)
zinc   = Contaminant(name="zinc",   trough_index=1, tip_index=1, stock_ppm=500,  tip_box_deck_slot=2)
iron   = Contaminant(name="iron",   trough_index=2, tip_index=2, stock_ppm=2000, tip_box_deck_slot=2)
lead   = Contaminant(name="lead",   trough_index=3, tip_index=3, stock_ppm=800,  tip_box_deck_slot=2)

PLATE_NAME           = "omen_double_sample_well_plate"
DILUENT_TROUGH_INDEX = 3
DILUENT_VOLUME_UL    = 900
DILUENT_TIP_BOX_SLOT = 2
TROUGH_DECK_SLOT     = 3

TIP_BOX_SLOTS = {
    # 20:   5,
    300:  2,
    # 1000: 6,
}


@plac.annotations(
    servicer_url=servicer_url_annotation,
    output_file_path=output_file_path_annotation,
)
def main(
    servicer_url: str = DEFAULT_SERVICER_URL,
    output_file_path: pathlib.Path | None = None,
) -> None:
    client = TCodeServicerClient(servicer_url=servicer_url)

    # Plate 1 — deck slot 4
    # well 0 gets copper + zinc, well 1 gets iron + lead
    print("Preparing plate 1:")
    script = multi_sample_creation(
        well_configs=[
            WellConfig(
                well_index=0,
                contaminant_ppms=[
                    ContaminantTargetPPM(contaminant=copper, target_ppm=10),
                    ContaminantTargetPPM(contaminant=zinc,   target_ppm=5),
                ],
                diluent_tip_index=4,
            ),
            WellConfig(
                well_index=1,
                contaminant_ppms=[
                    ContaminantTargetPPM(contaminant=iron, target_ppm=2),
                    ContaminantTargetPPM(contaminant=lead, target_ppm=8),
                ],
                diluent_tip_index=5,
            ),
        ],
        diluent_trough_index=DILUENT_TROUGH_INDEX,
        diluent_volume_ul=DILUENT_VOLUME_UL,
        tip_box_slots=TIP_BOX_SLOTS,
        diluent_tip_box_deck_slot=DILUENT_TIP_BOX_SLOT,
        well_plate_name=PLATE_NAME,
        well_plate_deck_slot=4,
        trough_deck_slot=TROUGH_DECK_SLOT,
    )
    client.run_script(script)

    # Plate 2 — deck slot 5
    # well 0 gets copper + iron, well 1 gets zinc + lead
    print("Preparing plate 2:")
    script = multi_sample_creation(
        well_configs=[
            WellConfig(
                well_index=0,
                contaminant_ppms=[
                    ContaminantTargetPPM(contaminant=copper, target_ppm=15),
                    ContaminantTargetPPM(contaminant=iron,   target_ppm=3),
                ],
                diluent_tip_index=6,
            ),
            WellConfig(
                well_index=1,
                contaminant_ppms=[
                    ContaminantTargetPPM(contaminant=zinc, target_ppm=7),
                    ContaminantTargetPPM(contaminant=lead, target_ppm=4),
                ],
                diluent_tip_index=7,
            ),
        ],
        diluent_trough_index=DILUENT_TROUGH_INDEX,
        diluent_volume_ul=DILUENT_VOLUME_UL,
        tip_box_slots=TIP_BOX_SLOTS,
        diluent_tip_box_deck_slot=DILUENT_TIP_BOX_SLOT,
        well_plate_name=PLATE_NAME,
        well_plate_deck_slot=5,
        trough_deck_slot=TROUGH_DECK_SLOT,
    )
    client.run_script(script)


if __name__ == "__main__":
    plac.call(main)