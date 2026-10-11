-- Add text search columns for file name and parent directory
ALTER TABLE photos
  ADD COLUMN file_name VARCHAR(255) NULL,
  ADD COLUMN parent_dir_name VARCHAR(255) NULL;

-- Backfill from file_path (Windows paths supported)
UPDATE photos
SET
  file_name = SUBSTRING_INDEX(REPLACE(file_path, '\\', '/'), '/', -1),
  parent_dir_name = SUBSTRING_INDEX(
                      SUBSTRING_INDEX(REPLACE(file_path, '\\', '/'), '/', -2),
                      '/',
                      1
                    )
WHERE file_name IS NULL OR file_name = ''
   OR parent_dir_name IS NULL OR parent_dir_name = '';

-- Optional indexes for faster lookups
CREATE INDEX idx_file_name ON photos (file_name);
CREATE INDEX idx_parent_dir_name ON photos (parent_dir_name);
