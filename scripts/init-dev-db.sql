-- Development database initialization
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create development user with limited permissions
CREATE USER indra_dev_readonly WITH PASSWORD 'readonly123';

-- Grant read-only access to development user
GRANT CONNECT ON DATABASE indra_dev TO indra_dev_readonly;
GRANT USAGE ON SCHEMA public TO indra_dev_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO indra_dev_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO indra_dev_readonly;

-- Create sample data for development
INSERT INTO scraped_content (source, url, title, content, content_hash, scraped_at) VALUES
('sample_source', 'https://example.com/1', 'Sample Article 1', 'This is sample content for development testing.', 'hash1', NOW()),
('sample_source', 'https://example.com/2', 'Sample Article 2', 'This is another sample content for development.', 'hash2', NOW());
