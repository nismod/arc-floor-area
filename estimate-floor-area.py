"""Estimate floor area projections based on GVA and dwellings/households

First cut estimate for energy demand model input.

Requires inputs:
- dwellings scenarios (see `arc-dwellings`)
- gva scenarios (see `arc-economics`)
"""
import glob
import os
import sys

import pandas

# Numbers from RIBA Case for Space Report
AVERAGE_DWELLING_M2 = 85  # based on average home size
AVERAGE_NONRES_M2_PER_MGBP_GVA = 1  # based on no data, used in elasticity-based model
FUTURE_SCENARIOS = [
    {'scenario': 'base', 'average_dwelling_m2': AVERAGE_DWELLING_M2},
    {'scenario': 'compact', 'average_dwelling_m2': 76},  # average new build UK
    {'scenario': 'expand', 'average_dwelling_m2': 115},  # average new build NL
]


def main(base_path):
    data_path = os.path.join(base_path, 'data_as_provided')
    output_path = os.path.join(base_path, 'data_processed')

    dwellings_filenames = glob.glob(os.path.join(data_path, 'arc_dwellings__*.csv'))

    for d in dwellings_filenames:
        print("Processing", d)
        key = os.path.basename(d).replace('arc_dwellings__', '').replace('.csv', '')

        # HACK hard-code match for economics scenarios against 23k dwellings scenarios
        if "new-cities" in key:
            econ_key = "1-new-cities"
        elif key == "4-expansion23":
            econ_key = "2-expansion"
        else:
            econ_key = key
        e = os.path.join(data_path, 'arc_gva__{}.csv'.format(econ_key))

        d_df = pandas.read_csv(d)
        e_df = pandas.read_csv(e)

        for scenario in FUTURE_SCENARIOS:
            f_df = estimate_floor_area(d_df, e_df, scenario['average_dwelling_m2'])
            print(len(f_df), len(f_df.timestep.unique()), len(f_df.lad_uk_2016.unique()))
            f_df.to_csv(
                os.path.join(
                    output_path,
                    'arc_floor_area__{}__{}.csv'.format(key, scenario['scenario'])
                ),
                index=False
            )


def estimate_floor_area(dwellings, gva, future_average_dwelling_m2):
    # merge dwellings and gva for calculation
    floor_area = dwellings.merge(gva, on=['timestep', 'lad_uk_2016'])

    # filter down to base year
    floor_area_base = floor_area[floor_area.timestep == floor_area.timestep.min()].copy()

    # merge base year back on
    floor_area = floor_area.merge(
        floor_area_base,
        how='left',
        validate='many_to_one',
        on=['lad_uk_2016'],
        suffixes=('', '_base')
    )

    # calculate new dwellings (since base year)
    floor_area['dwellings_new'] = floor_area.dwellings - floor_area.dwellings_base

    # Residential floor area as (base * base average + future * future average)
    floor_area['residential'] = (
        floor_area.dwellings_base * AVERAGE_DWELLING_M2
        + floor_area.dwellings_new * future_average_dwelling_m2
    )

    # Non-residential floor area as (gva * average)
    floor_area['non_residential'] = floor_area.gva * AVERAGE_NONRES_M2_PER_MGBP_GVA

    # create residential_or_non indicator column
    floor_area = floor_area[
        ['timestep', 'lad_uk_2016', 'residential' ,'non_residential']
    ].melt(
        id_vars=['timestep', 'lad_uk_2016'],
        var_name='residential_or_non',
        value_name='floor_area'
    )

    return floor_area


if __name__ == '__main__':
    try:
        BASE_PATH = sys.argv[1]
    except:
        print("Usage: python {} <base_path>".format(__file__))
        exit(-1)

    main(BASE_PATH)
