-- Password policy scope upgrade
-- Date: 2026-03-11
-- Purpose:
-- 1. isolate standard photos by policy_id
-- 2. isolate favorites by policy_id
-- 3. keep existing data under admin policy

ALTER TABLE standard_photo
  ADD COLUMN IF NOT EXISTS policy_id VARCHAR(64) NOT NULL DEFAULT 'admin' AFTER id;

UPDATE standard_photo
SET policy_id = 'admin'
WHERE policy_id IS NULL OR policy_id = '';

ALTER TABLE standard_photo
  ADD INDEX IF NOT EXISTS idx_standard_photo_photo_id (photo_id);

ALTER TABLE standard_photo
  DROP INDEX IF EXISTS uk_standard_photo_photo_id;

ALTER TABLE standard_photo
  ADD UNIQUE INDEX IF NOT EXISTS uk_standard_photo_policy_photo_id (policy_id, photo_id);

ALTER TABLE standard_photo
  ADD INDEX IF NOT EXISTS idx_standard_photo_policy_id (policy_id);

ALTER TABLE favorites
  ADD COLUMN IF NOT EXISTS policy_id VARCHAR(64) NOT NULL DEFAULT 'admin' AFTER id;

UPDATE favorites
SET policy_id = 'admin'
WHERE policy_id IS NULL OR policy_id = '';

ALTER TABLE favorites
  ADD INDEX IF NOT EXISTS idx_favorites_policy_id (policy_id);

CREATE TABLE IF NOT EXISTS favorite_faces (
  favorite_id BIGINT NOT NULL,
  face_id BIGINT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (favorite_id, face_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
