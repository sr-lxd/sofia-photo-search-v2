ALTER TABLE photos
  ADD COLUMN IF NOT EXISTS gps_lat DECIMAL(10,7) NULL AFTER height;

ALTER TABLE photos
  ADD COLUMN IF NOT EXISTS gps_lon DECIMAL(10,7) NULL AFTER gps_lat;

ALTER TABLE photos
  ADD COLUMN IF NOT EXISTS gps_checked TINYINT(1) NOT NULL DEFAULT 0 AFTER gps_lon;

ALTER TABLE photos
  ADD INDEX IF NOT EXISTS idx_gps_lat_lon (gps_lat, gps_lon);

UPDATE photos
SET gps_checked=1
WHERE gps_checked=0
  AND gps_lat IS NOT NULL
  AND gps_lon IS NOT NULL;
