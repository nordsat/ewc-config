#!/usr/bin/env python

import os
import sys
import datetime
import rasterio
import geopandas as gpd
from shapely.geometry import box

try:
    geotiff_directory = sys.argv[1]
except Exception:
    print("missing input getiff diretory")
    raise
outdir = sys.argv[3]
df = gpd.GeoDataFrame(columns=['location', 'geometry', 'time'])
now = datetime.datetime.now()
for directory, subdir, files in os.walk(geotiff_directory):
    for fname in sorted(files):
        print(fname)
        file_to_handle = os.path.join(directory, fname)
        mtime = datetime.datetime.fromtimestamp(os.stat(file_to_handle).st_mtime)
        # if now - datetime.timedelta(hours=48) < mtime:
        if 1:
            print(file_to_handle)
            try:
                # If third argument is given pass if filename start with this string
                if fname.startswith(sys.argv[4]):
                    pass
                else:
                    continue
            except IndexError:
                # No third argument was given
                pass
            if fname.endswith(".tif"):
                dataset = rasterio.open(file_to_handle)
                print(dataset)
                print("META", dataset.meta)
                print("META CRS", dataset.meta['crs'])
                print("CRS", dataset.crs)
                tags = dataset.tags()
                # print("TIFFTAG_DATETIME", tags['TIFFTAG_DATETIME'], type(tags['TIFFTAG_DATETIME']))
                img_time = datetime.datetime.strptime(tags['TIFFTAG_DATETIME'], '%Y:%m:%d %H:%M:%S')
                img_end_time = datetime.datetime.strptime(tags['TIFFTAG_DATETIME'], '%Y:%m:%d %H:%M:%S') + datetime.timedelta(minutes=20)
                time_range = img_time.strftime('%Y-%m-%dT%H:%M:%SZ') + '/' + img_end_time.strftime('%Y-%m-%dT%H:%M:%SZ')
                # print(img_time)
                bounds = dataset.bounds
                # print(bounds)
                crs = dataset.crs
                df = df.append({'location': os.path.join(outdir, fname),
                                'geometry': box(bounds[0], bounds[1], bounds[2], bounds[3]),
                                'time': img_time.strftime('%Y-%m-%dT%H:%M:%SZ')},
                               ignore_index=True)
                df.crs = dataset.crs
        # break
try:
    df.to_file(os.path.join("./tile_index", sys.argv[2] + ".shp"))
except ValueError:
    print("No data to write to shape file")
