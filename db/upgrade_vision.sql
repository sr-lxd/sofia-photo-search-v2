-- ????????????????
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
