-- Initialize the database with optimized schema
CREATE TABLE IF NOT EXISTS job_postings (
    id SERIAL PRIMARY KEY,
    position_title TEXT NOT NULL,
    position_uri TEXT NOT NULL UNIQUE,
    position_location TEXT,
    position_remuneration TEXT,
    position_start_date DATE,
    position_end_date DATE,
    organization_name TEXT,
    department_name TEXT,
    job_category TEXT,
    job_grade TEXT,
    extracted_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_job_postings_title ON job_postings USING gin(to_tsvector('english', position_title));
CREATE INDEX IF NOT EXISTS idx_job_postings_location ON job_postings(position_location);
CREATE INDEX IF NOT EXISTS idx_job_postings_created_at ON job_postings(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_job_postings_organization ON job_postings(organization_name);
CREATE INDEX IF NOT EXISTS idx_job_postings_extracted_at ON job_postings(extracted_at DESC);
CREATE INDEX IF NOT EXISTS idx_job_postings_uri ON job_postings(position_uri);

-- Create a function to automatically update the updated_at column
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger for automatic timestamp updates
DROP TRIGGER IF EXISTS update_job_postings_updated_at ON job_postings;
CREATE TRIGGER update_job_postings_updated_at
    BEFORE UPDATE ON job_postings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Create a view for recent job postings
CREATE OR REPLACE VIEW recent_job_postings AS
SELECT 
    id,
    position_title,
    position_location,
    position_remuneration,
    organization_name,
    department_name,
    job_category,
    created_at,
    updated_at
FROM job_postings
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY created_at DESC;

-- Create a view for job statistics
CREATE OR REPLACE VIEW job_statistics AS
SELECT 
    COUNT(*) as total_jobs,
    COUNT(DISTINCT organization_name) as unique_organizations,
    COUNT(DISTINCT department_name) as unique_departments,
    COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE) as jobs_today,
    COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE - INTERVAL '7 days') as jobs_this_week,
    COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE - INTERVAL '30 days') as jobs_this_month,
    MAX(created_at) as last_job_date,
    MIN(created_at) as first_job_date
FROM job_postings;

-- Insert some sample metadata
CREATE TABLE IF NOT EXISTS etl_metadata (
    id SERIAL PRIMARY KEY,
    last_run_at TIMESTAMP WITH TIME ZONE,
    jobs_processed INTEGER,
    status VARCHAR(50),
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Grant necessary permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON job_postings TO postgres;
GRANT SELECT ON recent_job_postings TO postgres;
GRANT SELECT ON job_statistics TO postgres;
GRANT SELECT, INSERT, UPDATE, DELETE ON etl_metadata TO postgres;
