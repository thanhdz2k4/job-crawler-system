# Qdrant Vector Database Integration

## Tổng quan

Module này tích hợp Qdrant vector database vào job crawler system để:
- Tự động embedding job postings (position/title)
- Lưu trữ vector embeddings cho semantic search
- Sync dữ liệu từ MongoDB sang Qdrant
- Hỗ trợ tìm kiếm jobs bằng AI/ML

## Kiến trúc

```
Job Crawler → ValidationPipeline → CleaningPipeline → MongoPipeline → QdrantPipeline
                                                           ↓              ↓
                                                       MongoDB        Qdrant
                                                                         ↓
                                                              Embedding Service
```

## Components

### 1. Connection Factories

#### `config/qdrant_connections.py`
- Factory pattern để quản lý Qdrant client
- Singleton pattern đảm bảo một connection duy nhất
- Auto-create collection nếu chưa tồn tại

```python
from config.qdrant_connections import get_qdrant_client, get_collection_name

client = get_qdrant_client()
collection = get_collection_name()
```

#### `config/embedding_connections.py`
- Factory pattern để quản lý Embedding service client
- Retry mechanism và connection pooling
- Batch processing support

```python
from config.embedding_connections import get_embedding, get_embeddings_batch

# Single embedding
vector = get_embedding("Python Developer")

# Batch embedding
vectors = get_embeddings_batch(["Job 1", "Job 2", "Job 3"])
```

### 2. Qdrant Wrapper

#### `src/utils/qdrant_wrapper.py`
- High-level wrapper cho job operations
- Auto-embedding: position/title → vector
- Full payload storage

**Features:**
- ✅ Auto-embed jobs (position only)
- ✅ Upsert jobs với UUID point ID
- ✅ Search similar jobs by text
- ✅ Search by position (skills stored in payload for filtering)
- ✅ Batch operations
- ✅ MongoDB ObjectId support

```python
from src.utils.qdrant_wrapper import QdrantJobWrapper

wrapper = QdrantJobWrapper()

# Insert job
job_data = {
    'title': 'Python Developer',
    'skills': ['Python', 'Django', 'PostgreSQL'],
    'description': '...',
    'requirements': '...',
    'benefits': '...',
    'salary_raw': '15-20 triệu'
}

wrapper.upsert_job('job_id_123', job_data)

# Search similar jobs
results = wrapper.search_similar_jobs(
    query_text="Python Backend Developer với Django",
    limit=10,
    score_threshold=0.7
)
```

### 3. Scrapy Pipeline Integration

#### `src/crawlers/common/pipelines.py` - `QdrantPipeline`
- Tự động sync jobs từ MongoDB sang Qdrant
- Chạy sau MongoPipeline
- Graceful error handling

```python
# settings.py
ITEM_PIPELINES = {
    'src.crawlers.common.pipelines.ValidationPipeline': 100,
    'src.crawlers.common.pipelines.CleaningPipeline': 200,
    'src.crawlers.common.pipelines.MongoPipeline': 300,
    'src.crawlers.common.pipelines.QdrantPipeline': 400,  # ← Qdrant sync
}

ENABLE_QDRANT = True  # Enable/disable Qdrant sync
```

## Configuration

### `config/settings.yaml`

```yaml
# Qdrant Configuration
qdrant:
  host: "192.168.10.211"
  port: 6333  # HTTP port
  collection_name: "job_descriptions"
  timeout: 5000
  prefer_grpc: false
  vector_size: 768
  distance: "Cosine"

# Embedding Service Configuration
embedding:
  base_url: "http://192.168.10.29:31113"
  embed_path: "/embed"
  model: "dangvantuan/vietnamese-embedding"
  dimension: 768
  timeout: 30000
  max_retries: 3
  batch_size: 32
```

### Environment Variables

```bash
# Qdrant
export QDRANT_HOST="192.168.10.211"
export QDRANT_PORT="6333"
export QDRANT_COLLECTION="job_descriptions"

# Embedding Service
export EMBEDDING_BASE_URL="http://192.168.10.29:31113"
```

## Data Schema

### Qdrant Payload Structure

```json
{
  "positionName": "Senior Python Developer",
  "skills": ["Python", "Django", "PostgreSQL", "Docker", "AWS"],
  "salary_raw": "20-30 triệu VND",
  "jobDescriptionText": "Full job description...",
  "benefits": "Competitive salary, health insurance...",
  "requirements": "3+ years experience with Python...",
  "company": "TechCorp Vietnam",
  "location": "Hà Nội",
  "url": "https://example.com/job/123",
  "source": "topcv",
  "crawl_timestamp": "2024-12-05T10:00:00",
  "last_seen_timestamp": "2024-12-05T10:00:00"
}
```

### Vector Embedding

**Input:** `{positionName}`

Example:
```
"Senior Python Developer"
```

**Output:** Vector 768 dimensions (float32)

## Usage Examples

### 1. Standalone Usage

```python
from src.utils.qdrant_wrapper import QdrantJobWrapper

wrapper = QdrantJobWrapper()

# Insert single job
job = {
    'title': 'Backend Developer',
    'skills': ['Python', 'FastAPI'],
    'description': 'Looking for Backend Developer...',
    'salary_raw': '15-20 triệu',
    # ... other fields
}
wrapper.upsert_job('unique_job_id', job)

# Search
results = wrapper.search_similar_jobs("Python Developer", limit=5)
for job in results:
    print(f"{job['positionName']} - Score: {job['score']}")
```

### 2. Batch Operations

```python
# Insert batch
jobs = [
    {'_id': 'id1', 'title': 'Job 1', ...},
    {'_id': 'id2', 'title': 'Job 2', ...},
]
stats = wrapper.upsert_jobs_batch(jobs, id_field='_id')
print(f"Success: {stats['success']}, Failed: {stats['failed']}")
```

### 3. Search by Position

```python
# `skills` là optional, embedding chỉ dùng position/title
results = wrapper.search_by_position_and_skills(
    position="Data Engineer",
    skills=["Python", "Spark", "Airflow"],
    limit=10
)
```

### 4. Integration with MongoDB

```python
from config.connections import get_collection
from src.utils.qdrant_wrapper import QdrantJobWrapper

# Get MongoDB collection
mongo_collection = get_collection('raw_data')
wrapper = QdrantJobWrapper()

# Sync all jobs
for job in mongo_collection.find({'metadata.is_active': True}):
    wrapper.upsert_job(job['_id'], job)
```

## Testing

### Test Connections

```bash
# Test Qdrant connection
cd job_crawler_system
python config/qdrant_connections.py

# Test Embedding service
python config/embedding_connections.py

# Test Qdrant wrapper
python -m src.utils.qdrant_wrapper
```

### Expected Output

```
============================================================
Testing Qdrant Job Wrapper
============================================================

1. Initializing wrapper...
   [OK] Wrapper initialized with collection: job_descriptions

2. Counting existing jobs...
   Current jobs count: 1

3. Inserting test job...
   [OK] Job inserted with ID: test_job_001

4. Retrieving job...
   [OK] Retrieved job: Senior Python Developer
   Skills: ['Python', 'Django', 'PostgreSQL', 'Docker', 'AWS']

5. Searching similar jobs...
   Found 2 similar jobs:
   1. Senior Python Developer - Score: 0.987
   2. Backend Python Engineer - Score: 0.856

...

[SUCCESS] All tests passed successfully
```

## Monitoring & Debugging

### Check Qdrant Stats

```python
from config.qdrant_connections import get_qdrant_client

client = get_qdrant_client()
info = client.get_collection('job_descriptions')
print(f"Points count: {info.points_count}")
print(f"Vectors count: {info.vectors_count}")
```

### Pipeline Statistics

Khi crawler chạy, check logs:

```
QdrantPipeline stats: synced=150, failed=5, skipped=0
```

### Common Issues

1. **Connection timeout**
   - Check network connectivity
   - Verify Qdrant server is running
   - Increase timeout in settings.yaml

2. **Embedding failed**
   - Check embedding service status
   - Verify text is not empty
   - Check max_retries setting

3. **Invalid point ID**
   - Ensure job_id is valid UUID or can be converted
   - Check _convert_job_id() method

## Performance Tips

1. **Batch Operations:** Use `upsert_jobs_batch()` cho nhiều jobs
2. **Async Processing:** Consider sử dụng async version (future enhancement)
3. **Caching:** Cache embeddings cho repeated queries
4. **Indexing:** Qdrant tự động index, không cần config thêm

## Future Enhancements

- [ ] Async operations support
- [ ] Incremental updates (chỉ update nếu content thay đổi)
- [ ] Filtering by metadata (salary range, location, etc.)
- [ ] Hybrid search (vector + keyword)
- [ ] Recommendation system
- [ ] A/B testing cho embedding models

## References

- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [Qdrant Python Client](https://github.com/qdrant/qdrant-client)
- [Vietnamese Embedding Model](https://huggingface.co/dangvantuan/vietnamese-embedding)
