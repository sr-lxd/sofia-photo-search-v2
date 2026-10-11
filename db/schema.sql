CREATE TABLE IF NOT EXISTS photos (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  file_path VARCHAR(768) NOT NULL UNIQUE,
  file_name VARCHAR(255) NULL,
  parent_dir_name VARCHAR(255) NULL,
  file_hash CHAR(32) NOT NULL,
  file_size BIGINT NOT NULL,
  exif_datetime DATETIME NULL,
  file_mtime DATETIME NOT NULL,
  width INT NULL,
  height INT NULL,
  gps_lat DECIMAL(10,7) NULL,
  gps_lon DECIMAL(10,7) NULL,
  gps_checked TINYINT(1) NOT NULL DEFAULT 0,
  face_count INT DEFAULT 0,
  status ENUM('active','deleted') DEFAULT 'active',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_mtime (file_mtime),
  INDEX idx_exif (exif_datetime),
  INDEX idx_gps_lat_lon (gps_lat, gps_lon),
  INDEX idx_file_name (file_name),
  INDEX idx_parent_dir_name (parent_dir_name),
  INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS faces (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  photo_id BIGINT NOT NULL,
  face_index INT NOT NULL,
  bbox_x1 INT NOT NULL,
  bbox_y1 INT NOT NULL,
  bbox_x2 INT NOT NULL,
  bbox_y2 INT NOT NULL,
  embedding_id BIGINT NOT NULL,
  model_name VARCHAR(64) NOT NULL,
  quality_score FLOAT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_photo_id (photo_id),
  INDEX idx_embedding_id (embedding_id),
  CONSTRAINT fk_faces_photos FOREIGN KEY (photo_id) REFERENCES photos(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS index_state (
  id INT PRIMARY KEY AUTO_INCREMENT,
  index_path VARCHAR(1024) NOT NULL,
  index_type VARCHAR(64) NOT NULL,
  last_embedding_id BIGINT NOT NULL,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS favorites (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  policy_id VARCHAR(64) NOT NULL DEFAULT 'admin',
  name VARCHAR(128) NOT NULL,
  cover_face_id BIGINT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_favorites_policy_id (policy_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS favorite_faces (
  favorite_id BIGINT NOT NULL,
  face_id BIGINT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (favorite_id, face_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS standard_photo (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  policy_id VARCHAR(64) NOT NULL DEFAULT 'admin',
  photo_id BIGINT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_standard_photo_policy_photo_id (policy_id, photo_id),
  INDEX idx_standard_photo_photo_id (photo_id),
  INDEX idx_standard_photo_policy_id (policy_id),
  CONSTRAINT fk_standard_photo_photos FOREIGN KEY (photo_id) REFERENCES photos(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS photo_embeddings (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  photo_id BIGINT NOT NULL UNIQUE,
  embedding_id BIGINT NOT NULL UNIQUE,
  model_name VARCHAR(64) NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_embedding_id (embedding_id),
  INDEX idx_photo_id (photo_id),
  CONSTRAINT fk_photo_embeddings_photos FOREIGN KEY (photo_id) REFERENCES photos(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS index_state_vision (
  id INT PRIMARY KEY AUTO_INCREMENT,
  index_path VARCHAR(1024) NOT NULL,
  index_type VARCHAR(64) NOT NULL,
  last_embedding_id BIGINT NOT NULL,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS scan_progress (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  scan_type VARCHAR(16) NOT NULL,
  processed_photos BIGINT NOT NULL DEFAULT 0,
  total_photos BIGINT NOT NULL DEFAULT 0,
  last_path VARCHAR(768) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'running',
  started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_status (status),
  INDEX idx_started (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS scan_seen (
  file_path VARCHAR(768) PRIMARY KEY
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS scan_failed (
  file_path VARCHAR(768) PRIMARY KEY,
  file_size BIGINT NOT NULL,
  file_mtime DATETIME NOT NULL,
  error_type VARCHAR(64) NULL,
  error_message VARCHAR(255) NULL,
  failed_count INT NOT NULL DEFAULT 1,
  first_failed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  last_failed_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_last_failed_at (last_failed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
