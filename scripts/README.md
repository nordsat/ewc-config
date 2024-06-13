# db-sync

# postgis

## deploy container
```
podman run -d --replace --rm --name postgis --network pytroll_network -e POSTGRES_PASSWORD=pytroll postgis/postgis

```

## table to be created in postgis db
CREATE TABLE products (filename varchar, product_name varchar, time timestamp, geom geometry);

# sync-db

## build container

```
podman build -t db-sync .
```

## deploy container to run sync-db

```
podman run -d --replace  --name db-sync --network pytroll_network -v /eodata/hrit_out/:/mnt/output/  -v ./db-and-mapfile-handle.yaml:/usr/local/bin/db-sync/db-and-mapfile-handle.yaml -v ./db-and-mapfile-handle.py:/usr/local/bin/db-sync/db-and-mapfile-handle.py db-sync python3 db-and-mapfile-handle.py db-and-mapfile-handle.yaml
```

# mapserver

## deploy container
```
podman run --replace --name mapserver -d --rm --network pytroll_network -v /eodata/hrit_out:/data -v /root/seviri-processing/maps/:/etc/mapserver/ docker.io/camptocamp/mapserver 
```

Verify that all containers are in the same network
```
podman ps --filter network=pytroll_network 
```

