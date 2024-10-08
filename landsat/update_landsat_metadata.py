# =============================================================================================
# Copyright 2018 dgketchum
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =============================================================================================
from __future__ import print_function, absolute_import

import gzip
import os
from datetime import datetime
import pandas as pd
from pandas.errors import EmptyDataError
from fastparquet import write
from zipfile import ZipFile, BadZipFile
from fastkml import kml

from dask.dataframe import read_csv
from numpy import unique
from requests import get

fmt = '%Y%m%d'
date = datetime.strftime(datetime.now(), fmt)

class SatMetaData(object):
    """ ... """

    def __init__(self, sat):

        if sat == 'landsat':
            self.sat = 'landsat'
            self.metadata_url = 'http://storage.googleapis.com/gcp-public-data-landsat/index.csv.gz'
            self.vector_url = ['https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/'
                               's3fs-public/atoms/files/WRS1_descending_0.zip',
                               'https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/'
                               's3fs-public/atoms/files/WRS2_descending_0.zip']
            self.project_ws = os.path.dirname(__file__)
            self.vector_files = (os.path.join(self.project_ws, 'wrs', 'wrs1_descending.shp'),
                                 os.path.join(self.project_ws, 'wrs', 'wrs2_descending.shp'))
            self.vector_zip = os.path.join(self.project_ws, 'wrs', 'wrs.zip')
            self.vector_dir = os.path.join(self.project_ws, 'wrs')
            self.scenes = os.path.join(self.project_ws, 'scenes')
            self.scenes_zip = os.path.join(self.scenes, 'l_index.csv.gz')
            self.latest = os.path.join(self.scenes, 'scenes_{}'.format(date))

        else:
            raise NotImplementedError('only works for "landsat"')

    def update_metadata_lists(self):
        print('Please wait while Landsat578 updates {} metadata files...'.format(self.sat))
        if not os.path.isdir(self.scenes):
            os.mkdir(self.scenes)
        os.chdir(self.scenes)
        ls = os.listdir(self.scenes)
        for f in ls:
            if 'l_scenes_' in f and self.latest not in f:
                os.remove(os.path.join(self.scenes, f))
        self.download_latest_metadata()
        try:
            os.remove(self.latest)
            os.remove(self.scenes_zip)
        except FileNotFoundError:
            pass
        with open(self.latest, 'w') as empty:
            empty.write('')
        return None

    def download_latest_metadata(self):

        if not os.path.isfile(self.latest):
            req = get(self.metadata_url, stream=True)
            if req.status_code != 200:
                raise ValueError('Bad response {} from request.'.format(req.status_code))

            with open(self.scenes_zip, 'wb') as f:
                print('Downloading {}'.format(self.metadata_url))
                for chunk in req.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)

            self.split_list()
            self.get_wrs_shapefiles()

        else:
            print('you have the latest {} metadata'.format(self.sat))

        if not os.path.isfile(self.latest):
            with gzip.open(self.scenes_zip, 'rb') as infile:
                print('unzipping {}'.format(self.scenes_zip))
                with open(self.latest, 'wb') as outfile:
                    for line in infile:
                        outfile.write(line)

        return None

    def split_list(self):

        print('Please wait while {} scene metadata is split'.format(self.sat))
        chunksize = 250000 # the number of rows per chunk
        print('Extracting satellites to ', self.scenes)
        processed_sats = []
        df = pd.read_csv(self.scenes_zip,
                         dtype={'PRODUCT_ID': object, 'COLLECTION_NUMBER': object, 'COLLECTION_CATEGORY': object},
                         parse_dates=True, chunksize=chunksize, iterator=True)
        loop = True
        while loop:
            try:
                chunk = df.get_chunk(chunksize)
                fc = chunk[chunk.COLLECTION_NUMBER != 'PRE']
                if fc.empty is True:
                    sats = []
                else:
                    sats = unique(fc.SPACECRAFT_ID).tolist()
                for sat in sats:
                    sfc = fc[fc.SPACECRAFT_ID == sat]
                    dst = os.path.join(self.scenes, sat)
                    if sat in processed_sats:
                        write(dst, sfc, append=True, compression='GZIP')
                    else:
                        print(sat)
                        if os.path.exists(dst):
                            os.remove(dst)
                        write(dst, sfc, compression='GZIP')
                        processed_sats.append(sat)
            except StopIteration:
                loop = False

        return None

    def get_wrs_shapefiles(self):
        if not os.path.isdir(self.vector_dir):
            os.mkdir(self.vector_dir)
        os.chdir(self.vector_dir)
        self.download_wrs_data()

    def download_wrs_data(self):
        for url, wrs_file in zip(self.vector_url, self.vector_files):
            if not os.path.isfile(wrs_file):
                req = get(url, stream=True)
                if req.status_code != 200:
                    raise ValueError('Bad response {} from request.'.format(req.status_code))

                with open(self.vector_zip, 'wb') as f:
                    print('Downloading {}'.format(url))
                    for chunk in req.iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)
            try:
                with ZipFile(self.vector_zip, 'r') as zip_file:
                    print('unzipping {}'.format(self.vector_zip))
                    zip_file.extractall()

            except BadZipFile:
                with open(self.vector_zip) as doc:
                    s = doc.read()
                    k = kml.KML()
                    k.from_string(s)
                    features = list(k.features())
                for f in features:
                    pass
            os.remove(self.vector_zip)

        return None


if __name__ == '__main__':
    pass

# ========================= EOF ================================================================
