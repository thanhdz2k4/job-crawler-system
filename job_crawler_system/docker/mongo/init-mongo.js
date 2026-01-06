// MongoDB initialization script
// This script runs when the MongoDB container starts for the first time

// Switch to the job_crawler_db database
db = db.getSiblingDB('job_crawler_db');

// Create a user for the application
db.createUser({
  user: 'job_crawler_user',
  pwd: 'job_crawler_pass',
  roles: [
    {
      role: 'readWrite',
      db: 'job_crawler_db'
    }
  ]
});

// Create collections
db.createCollection('job_postings_raw');
db.createCollection('job_postings_history');
db.createCollection('crawler_logs');

// Create indexes for job_postings_raw collection
db.job_postings_raw.createIndex(
  { "url": 1, "source": 1 },
  { unique: true, name: "idx_url_source_unique" }
);

db.job_postings_raw.createIndex(
  { "title": "text", "company": "text" },
  { name: "idx_text_search" }
);

db.job_postings_raw.createIndex(
  { "content_hash": 1 },
  { name: "idx_content_hash" }
);

db.job_postings_raw.createIndex(
  { "crawl_timestamp": -1 },
  { name: "idx_crawl_timestamp" }
);

db.job_postings_raw.createIndex(
  { "metadata.is_active": 1 },
  { name: "idx_is_active" }
);

// Create indexes for job_postings_history collection
db.job_postings_history.createIndex(
  { "original_id": 1, "version_timestamp": -1 },
  { name: "idx_history_lookup" }
);

// Create TTL index for crawler_logs collection (auto-delete after 30 days)
db.crawler_logs.createIndex(
  { "timestamp": 1 },
  { expireAfterSeconds: 2592000, name: "idx_logs_ttl" }
);

print('MongoDB initialization completed successfully');