"""TA regression, temporal boundaries, physical signs and immutable outputs."""
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd
import xarray as xr

from src.loader import load_gti_file
from src.estimator import AzimuthEstimator
from analysis.ta_full_period.run_full_period import (
    period, lookup_doy, estimate_date, row_ledger, lut_day, CONVENTION, uniform_minutes,
)

ROOT=Path(__file__).resolve().parents[1]


class TAPeriodTests(unittest.TestCase):
    def test_cadence_is_independent_of_pandas_storage_unit(self):
        index=pd.date_range('2017-01-01',periods=5,freq='min',tz='UTC')
        for unit in ['ns','us','ms','s']:
            self.assertTrue(uniform_minutes(index.as_unit(unit)))
            self.assertFalse(uniform_minutes(index.delete(2).as_unit(unit)))
            self.assertFalse(uniform_minutes(index.insert(2,index[2]).as_unit(unit)))

    def test_tilt_and_clock_boundaries(self):
        self.assertEqual(period('2015-09-05'), (45.0, 'GTI30_AV (W/m2)', 'UTC'))
        self.assertEqual(period('2016-09-26')[0], 45.0)
        self.assertEqual(period('2016-09-28'),(45,'GTI45_AV (W/m2)','UTC'))
        self.assertEqual(period('2017-05-11')[2],'UTC')
        self.assertEqual(period('2017-05-13')[2],'Etc/GMT+3')
        self.assertEqual(period('2018-10-10','utc')[2],'UTC')
        for date in ['2015-09-04','2018-10-11','2016-09-27','2017-05-12']:
            with self.assertRaises(ValueError):period(date)

    def test_reference_calendar_handles_leap_year(self):
        self.assertEqual(lookup_doy('2016-03-01'),(60,))
        self.assertEqual(lookup_doy('2016-12-31'),(365,))
        self.assertEqual(lookup_doy('2016-02-29'),(59,60))

    def test_explicit_loader_overrides_and_original_row_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'input.csv'
            raw=pd.DataFrame({'Timestamp':['2018/01/01 12:01:00.900','2018/01/01 12:00:00.200'],
                              'GHI1_AV (W/m2)':[900,901],'GTI30_AV (W/m2)':[800,801]})
            raw.to_csv(p,index=False)
            with self.assertRaises(ValueError):load_gti_file(p,'TA')
            local=load_gti_file(p,'TA',gti_col='GTI30_AV (W/m2)',source_tz='Etc/GMT+3')
            utc=load_gti_file(p,'TA',gti_col='GTI30_AV (W/m2)',source_tz='UTC')
            self.assertEqual(local.index[0].hour,12)
            self.assertEqual(utc.index[0].hour,9)
            pd.testing.assert_frame_equal(local,utc.set_axis(utc.index+pd.Timedelta(hours=3)))
            ledger=row_ledger(raw,local,'Etc/GMT+3','GTI30_AV (W/m2)','screening_rejected')
            self.assertEqual(ledger.row_id.tolist(),[0,1])
            self.assertEqual(ledger.csv_line.tolist(),[2,3])
            self.assertEqual(ledger.timestamp_raw.tolist(),raw.Timestamp.tolist())

    def test_plateau_sign_conversion_preserves_source_order(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'lut.nc'
            ds=xr.Dataset({'omega_star':(('azimuth','doy'),[[2,4],[2,4],[3,5]])},
                          coords={'azimuth':[10,11,12],'doy':[59,60]},
                          attrs={'station':'TA','surface_tilt':45})
            ds.to_netcdf(p)
            e=AzimuthEstimator(-31.74,-55.98,45,p,station='TA')
            self.assertEqual(e.estimate(2,59),10)
            self.assertEqual(e.estimate(2,59,tie_break='last'),11)
            self.assertEqual(estimate_date(e,3,'2016-02-29'),(11.,'feb29_midpoint_omega_curve'))
            with self.assertRaises(ValueError):e.estimate(2,59,tie_break='other')
            with self.assertRaises(ValueError):AzimuthEstimator(-31.74,-55.98,30,p)
            e.ds.close()

    def test_swc2021_physical_east_west_sign(self):
        for tilt in [30,45]:
            omega=lut_day(tilt,80,np.array([-20.,0.,20.]))
            self.assertLess(omega[0],-1)
            self.assertLess(abs(omega[1]),0.3)
            self.assertGreater(omega[2],1)

    def test_existing_ta_result_inversion(self):
        p=ROOT/'lookup/TA/lookup_omega_gamma_swc2021.nc'
        e=AzimuthEstimator(-31.74,-55.98,45,p,station='TA')
        self.assertEqual(e.ds.attrs['azimuth_convention'],CONVENTION)
        frame=pd.read_csv(ROOT/'outputs/TA/results/azimuth_results_20261103_204427_swc2021.csv')
        for row in frame.itertuples():
            gamma,_=estimate_date(e,row.omega_star,row.date)
            self.assertAlmostEqual(gamma,row.azimuth,places=10)
        e.ds.close()


if __name__=='__main__':unittest.main()
