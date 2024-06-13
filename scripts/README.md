# db-sync

# table to be created in postgis db
CREATE TABLE products (filename varchar, product_name varchar, time timestamp, geom geometry);

# container to run sync-db

```
podman run -d --replace  --name db-sync --network pytroll_network -v /eodata/hrit_out/:/mnt/output/  -v ./db-and-mapfile-handle.yaml:/usr/local/bin/db-sync/db-and-mapfile-handle.yaml -v ./db-and-mapfile-handle.py:/usr/local/bin/db-sync/db-and-mapfile-handle.py db-sync python3 db-and-mapfile-handle.py db-and-mapfile-handle.yaml
```
