# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (C) 2015-2017 GEM Foundation
#
# OpenQuake is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenQuake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with OpenQuake. If not, see <http://www.gnu.org/licenses/>.

"""
Disaggregation calculator core functionality
"""
from __future__ import division
import math
import logging
import numpy

from openquake.baselib.general import split_in_blocks, pack, AccumDict
from openquake.hazardlib.calc import disagg
from openquake.hazardlib.calc.filters import SourceFilter
from openquake.hazardlib.gsim.base import ContextMaker
from openquake.baselib import parallel
from openquake.hazardlib import sourceconverter
from openquake.commonlib import calc
from openquake.calculators import base, classical

DISAGG_RES_FMT = 'disagg/%(poe)srlz-%(rlz)s-%(imt)s-%(lon)s-%(lat)s/'


def compute_disagg(src_filter, sources, cmaker, imldict, trti, bin_edges,
                   oqparam, monitor):
    # see https://bugs.launchpad.net/oq-engine/+bug/1279247 for an explanation
    # of the algorithm used
    """
    :param src_filter:
        a :class:`openquake.hazardlib.calc.filter.SourceFilter` instance
    :param sources:
        list of hazardlib source objects
    :param cmaker:
        a :class:`openquake.hazardlib.gsim.base.ContextMaker` instance
    :param imldict:
        a list of dictionaries poe, gsim, imt, rlzi -> iml
    :param dict trti:
        tectonic region type index
    :param bin_egdes:
        a dictionary site_id -> edges
    :param oqparam:
        the parameters in the job.ini file
    :param monitor:
        monitor of the currently running job
    :returns:
        a dictionary of probability arrays, with composite key
        (sid, rlz.id, poe, imt, iml, trti).
    """
    sitecol = src_filter.sitecol
    result = {}  # sid, rlz.id, poe, imt, iml -> array

    collecting_mon = monitor('collecting bins')
    arranging_mon = monitor('arranging bins')

    for i, site in enumerate(sitecol):
        sid = sitecol.sids[i]
        try:
            edges = bin_edges[sid]
        except KeyError:
            # bin_edges for a given site are missing if the site is far away
            continue

        with collecting_mon:
            acc = disagg.collect_bins_data(
                sources, site, cmaker, imldict[i],
                oqparam.truncation_level, oqparam.num_epsilon_bins,
                monitor('disaggregate_pne', measuremem=False))
            bindata = pack(acc, 'mags dists lons lats'.split())
            if not bindata:
                continue

        with arranging_mon:  # this is fast
            for (poe, imt, iml, rlzi), matrix in disagg.build_disagg_matrix(
                    bindata, edges, arranging_mon).items():
                result[sid, rlzi, poe, imt, iml, trti] = matrix
        result['cache_info'] = arranging_mon.cache_info
    return result


def agg_probs(*probs):
    acc = 1.
    for prob in probs:
        acc *= 1. - prob
    return 1. - acc


@base.calculators.add('disaggregation')
class DisaggregationCalculator(base.HazardCalculator):
    """
    Classical PSHA disaggregation calculator
    """
    POE_TOO_BIG = '''\
You are trying to disaggregate for poe=%s.
However the source model #%d, '%s',
produces at most probabilities of %s for rlz=#%d, IMT=%s.
The disaggregation PoE is too big or your model is wrong,
producing too small PoEs.'''

    def execute(self):
        """Performs the disaggregation"""
        oq = self.oqparam
        if oq.iml_disagg:
            # no hazard curves are needed
            curves = [None] * len(self.sitecol)
        else:
            # only the poes_disagg are known, the IMLs are interpolated from
            # the hazard curves, hence the need to run a PSHACalculator here
            classical.PSHACalculator(oq, self.monitor('classical'),
                                     calc_id=self.datastore.calc_id).run()
            curves = [self.get_curves(sid) for sid in self.sitecol.sids]
            self.check_poes_disagg(curves)
        return self.full_disaggregation(curves)

    def agg_result(self, acc, result):
        """
        Collect the results coming from compute_disagg into self.results,
        a dictionary with key (sid, rlz.id, poe, imt, iml, trti)
        and values which are probability arrays.

        :param acc: dictionary k -> dic accumulating the results
        :param result: dictionary with the result coming from a task
        """
        if 'cache_info' in result:
            self.cache_info += result.pop('cache_info')
        for key, val in result.items():
            k, trti = key[:-1], key[-1]
            acc[k][trti] = 1. - (1. - acc[k].get(trti, 0)) * (1. - val)
        return acc

    def get_curves(self, sid):
        """
        Get all the relevant hazard curves for the given site ordinal.
        Returns a dictionary rlz_id -> curve_by_imt.
        """
        dic = {}
        imtls = self.oqparam.imtls
        pgetter = calc.PmapGetter(self.datastore, sids=numpy.array([sid]))
        for rlz in self.rlzs_assoc.realizations:
            try:
                pmap = pgetter.get(rlz.ordinal)
            except ValueError:  # empty pmaps
                logging.info(
                    'hazard curve contains all zero probabilities; '
                    'skipping site %d, rlz=%d', sid, rlz.ordinal)
                continue
            if sid not in pmap:
                continue
            poes = pmap[sid].convert(imtls)
            for imt_str in imtls:
                if all(x == 0.0 for x in poes[imt_str]):
                    logging.info(
                        'hazard curve contains all zero probabilities; '
                        'skipping site %d, rlz=%d, IMT=%s',
                        sid, rlz.ordinal, imt_str)
                    continue
                dic[rlz.ordinal] = poes
        return dic

    def check_poes_disagg(self, curves):
        """
        Raise an error if the given poes_disagg are too small compared to
        the hazard curves.
        """
        oq = self.oqparam

        # populate max_poe array
        max_poe = numpy.zeros(len(self.rlzs_assoc.realizations), oq.imt_dt())
        for sid, site in enumerate(self.sitecol):
            for rlzi, poes in curves[sid].items():
                for imt in oq.imtls:
                    max_poe[rlzi][imt] = max(
                        max_poe[rlzi][imt], poes[imt].max())

        # check for too big poes_disagg
        for smodel in self.csm.source_models:
            sm_id = smodel.ordinal
            for poe in oq.poes_disagg:
                for rlz in self.rlzs_assoc.rlzs_by_smodel[sm_id]:
                    rlzi = rlz.ordinal
                    for imt in oq.imtls:
                        min_poe = max_poe[rlzi][imt]
                        if poe > min_poe:
                            raise ValueError(self.POE_TOO_BIG % (
                                poe, sm_id, smodel.name, min_poe, rlzi, imt))

    def full_disaggregation(self, curves):
        """
        Run the disaggregation phase.

        :param curves: a list of hazard curves, one per site

        The curves can be all None if iml_disagg is set in the job.ini
        """
        oq = self.oqparam
        tl = oq.truncation_level
        sitecol = self.sitecol
        eps_edges = numpy.linspace(-tl, tl, oq.num_epsilon_bins + 1)

        self.bin_edges = {}
        # determine the number of source groups
        num_grps = sum(1 for sg in self.csm.src_groups)
        nblocks = math.ceil(oq.concurrent_tasks / num_grps)
        src_filter = SourceFilter(sitecol, oq.maximum_distance)

        # build trt_edges
        trts = tuple(sorted(set(sg.trt for smodel in self.csm.source_models
                                for sg in smodel.src_groups)))
        trt_num = {trt: i for i, trt in enumerate(trts)}
        self.trts = trts

        # build mag_edges
        min_mag = min(sg.min_mag for smodel in self.csm.source_models
                      for sg in smodel.src_groups)
        max_mag = max(sg.max_mag for smodel in self.csm.source_models
                      for sg in smodel.src_groups)
        mag_edges = oq.mag_bin_width * numpy.arange(
            int(numpy.floor(min_mag / oq.mag_bin_width)),
            int(numpy.ceil(max_mag / oq.mag_bin_width) + 1))

        # build dist_edges
        maxdist = max(oq.maximum_distance(trt, max_mag) for trt in trts)
        dist_edges = oq.distance_bin_width * numpy.arange(
            0, int(numpy.ceil(maxdist / oq.distance_bin_width) + 1))
        logging.info('dist = %s...%s', min(dist_edges), max(dist_edges))

        # build eps_edges
        eps_edges = numpy.linspace(-tl, tl, oq.num_epsilon_bins + 1)

        # build lon_edges, lat_edges per sid
        bbs = src_filter.get_bounding_boxes(mag=max_mag)
        for sid, bb in zip(self.sitecol.sids, bbs):
            lon_edges, lat_edges = disagg.lon_lat_bins(
                bb, oq.coordinate_bin_width)
            logging.info('site %d, lon = %s...%s',
                         sid, min(lon_edges), max(lon_edges))
            logging.info('site %d, lat = %s...%s',
                         sid, min(lat_edges), max(lat_edges))
            self.bin_edges[sid] = bs = (
                mag_edges, dist_edges, lon_edges, lat_edges, eps_edges)
            self.shape = [len(edges) - 1 for edges in bs]
            logging.info('%s for sid %d', self.shape + [len(trts)], sid)

        # build all_args
        all_args = []
        for smodel in self.csm.source_models:
            for sg in smodel.src_groups:
                split_sources = []
                for src in sg:
                    for split, _sites in src_filter(
                            sourceconverter.split_source(src), sitecol):
                        split_sources.append(split)
                if not split_sources:
                    continue
                mon = self.monitor('disaggregation')
                rlzs_by_gsim = self.rlzs_assoc.get_rlzs_by_gsim(
                    sg.trt, smodel.ordinal)
                cmaker = ContextMaker(
                    rlzs_by_gsim, src_filter.integration_distance)
                imls = [disagg.make_imldict(
                    rlzs_by_gsim, oq.imtls, oq.iml_disagg, oq.poes_disagg,
                    curve) for curve in curves]
                for srcs in split_in_blocks(split_sources, nblocks):
                    trti = trt_num[srcs[0].tectonic_region_type]
                    all_args.append(
                        (src_filter, srcs, cmaker, imls, trti,
                         self.bin_edges, oq, mon))

        self.cache_info = numpy.zeros(3)  # operations, cache_hits, num_zeros
        results = parallel.Starmap(compute_disagg, all_args).reduce(
            self.agg_result, AccumDict(accum={}))
        ops, hits, num_zeros = self.cache_info
        logging.info('Cache speedup %s', ops / (ops - hits))
        logging.info('Zero probabilities: %d', num_zeros)
        return results

    def post_execute(self, results):
        """
        Save all the results of the disaggregation. NB: the number of results
        to save is #sites * #rlzs * #disagg_poes * #IMTs.

        :param results:
            a dictionary of probability arrays
        """
        # save bin_edges
        dt = numpy.dtype([
            ('sid', numpy.uint32),
            ('mags', (float, self.shape[0] + 1)),
            ('dists', (float, self.shape[1] + 1)),
            ('lons', (float, self.shape[2] + 1)),
            ('lats', (float, self.shape[3] + 1)),
            ('eps', (float, self.shape[4] + 1)),
        ])
        arr = numpy.array(
            [(sid,) + mdlle for sid, mdlle in self.bin_edges.items()], dt)
        self.datastore['disagg-bins'] = arr

        # since an extremely small subset of the full disaggregation matrix
        # is saved this method can be run sequentially on the controller node
        logging.info('Extracting and saving the PMFs')
        for key, matrices in sorted(results.items()):
            sid, rlz_id, poe, imt, iml = key
            edges = self.bin_edges[sid]
            self.save_disagg_result(
                sid, edges, matrices, rlz_id,
                self.oqparam.investigation_time, imt, iml, poe)

    def save_disagg_result(self, site_id, bin_edges, matrices, rlz_id,
                           investigation_time, imt_str, iml, poe):
        """
        Save a computed disaggregation matrix to `hzrdr.disagg_result` (see
        :class:`~openquake.engine.db.models.DisaggResult`).

        :param site_id:
            id of the current site
        :param bin_edges:
            The 5-uple mag, dist, lon, lat, eps
        :param matrices:
            A dictionary trti -> disaggregation matrix
        :param rlz_id:
            ordinal of the realization to which the results belong.
        :param float investigation_time:
            Investigation time (years) for the calculation.
        :param imt_str:
            Intensity measure type string (PGA, SA, etc.)
        :param float iml:
            Intensity measure level interpolated (using `poe`) from the hazard
            curve at the `site`.
        :param float poe:
            Disaggregation probability of exceedance value for this result.
        """
        lon = self.sitecol.lons[site_id]
        lat = self.sitecol.lats[site_id]
        disp_name = DISAGG_RES_FMT % dict(
            poe='' if poe is None else 'poe-%s-' % poe,
            rlz=rlz_id, imt=imt_str, lon=lon, lat=lat)
        mon = self.monitor('extracting PMFs')
        mag, dist, lons, lats, eps = bin_edges
        matrix = agg_probs(*matrices.values())
        poe_agg = []
        num_trts = len(self.trts)
        for key, fn in disagg.pmf_map.items():
            with mon:
                if 'TRT' in key:
                    trti = next(iter(matrices))
                    a_pmf = fn(matrices[trti])
                    pmf = numpy.zeros(a_pmf.shape + (num_trts,))
                    pmf[..., trti] = a_pmf
                    for t in matrices:
                        if t != trti:
                            pmf[..., t] = fn(matrices[t])
                else:
                    pmf = fn(matrix)
            dname = disp_name + '_'.join(key)
            self.datastore[dname] = pmf
            poe_agg.append(1. - numpy.prod(1. - pmf))

        attrs = self.datastore.hdf5[disp_name].attrs
        attrs['rlzi'] = rlz_id
        attrs['imt'] = imt_str
        attrs['iml'] = iml
        attrs['mag_bin_edges'] = mag
        attrs['dist_bin_edges'] = dist
        attrs['lon_bin_edges'] = lons
        attrs['lat_bin_edges'] = lats
        attrs['eps_bin_edges'] = eps
        attrs['location'] = (lon, lat)
        # sanity check: all poe_agg should be the same
        attrs['poe_agg'] = poe_agg
        if poe is not None:
            attrs['poe'] = poe
