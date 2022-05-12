The container can be build using the Dockerfile from https://github.com/metno/mapserver-tools

Something like this: `sudo docker build . -t mapserver` in the container/mapserver directory

And you can start your container like this:
```
sudo docker run --rm -it -d --name mapserver -p 8080:8080/tcp -v /home/talonglong/shp-gen/tile_index/:/home/talonglong/shp-gen/tile_index/ -v /fci_data/data/output:/fci_data/data/output -v /home/talonglong/mapserver-config/geos-epsg:/usr/share/proj/geos-epsg -v /home/talonglong/mapserver-config/mapserver-test.map:/mapfile/mapfile.map mapserver
```

To build a shape file with data from various time steps ( you need the pytroll conda environment `source ~/mambaforge/bin/activate pytroll` as the bob user):

`python generate-shapefile.py /fci_data/data/output/ natural_color /fci_data/data/output/ natural_color`

To list the content of this shapefile:
`ogrinfo tile_index/natural_color.shp natural_color`
