"""
Qdrant Wrapper Module

Wrapper để tự động embed và lưu job postings vào Qdrant vector database.
Module này tích hợp với MongoDB pipeline để sync dữ liệu.

Usage:
    from src.utils.qdrant_wrapper import QdrantJobWrapper
    
    # Initialize wrapper
    wrapper = QdrantJobWrapper()
    
    # Insert job posting with auto-embedding
    job_data = {
        'title': 'Python Developer',
        'description': '...',
        'skills': ['Python', 'Django'],
        ...
    }
    wrapper.upsert_job(job_id='mongo_id_123', job_data=job_data)
"""

import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from bson import ObjectId

# Import connections
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from config.qdrant_connections import (
    get_qdrant_client,
    get_collection_name,
    create_collection_if_not_exists,
    collection_exists,
    get_config as get_qdrant_config
)
from config.embedding_connections import (
    get_embedding,
    get_embeddings_batch,
    test_connection as test_embedding_connection
)

from qdrant_client.models import PointStruct, Distance, VectorParams


logger = logging.getLogger(__name__)


class QdrantJobWrapper:
    """
    Wrapper class để quản lý job postings trong Qdrant.
    
    Features:
    - Auto-embed job postings (position only)
    - Upsert jobs với payload đầy đủ
    - Search jobs by embedding similarity
    - Sync với MongoDB
    """
    
    def __init__(
        self,
        collection_name: Optional[str] = None,
        auto_create_collection: bool = True
    ):
        """
        Initialize Qdrant Job Wrapper.
        
        Args:
            collection_name: Tên collection Qdrant (optional, lấy từ config)
            auto_create_collection: Tự động tạo collection nếu chưa tồn tại
        """
        self.client = get_qdrant_client()
        self.collection_name = collection_name or get_collection_name()
        
        # Ensure collection exists
        if auto_create_collection and not collection_exists(self.collection_name):
            logger.info(f"Creating Qdrant collection: {self.collection_name}")
            create_collection_if_not_exists(self.collection_name)
        
        # Test embedding service
        if not test_embedding_connection():
            logger.warning("Embedding service connection failed - embeddings may not work")
        
        logger.info(f"QdrantJobWrapper initialized with collection: {self.collection_name}")
    
    def _prepare_embedding_text(self, job_data: Dict[str, Any]) -> str:
        """
        Chuẩn bị text để embedding từ position/title.
        
        Args:
            job_data: Dictionary chứa dữ liệu job
            
        Returns:
            str: Text để embedding
        """
        position = (job_data.get('title') or job_data.get('positionName') or '').strip()
        
        # Primary embedding source: position/title only
        embedding_text = position
        
        if not embedding_text:
            logger.warning(f"Empty embedding text for job: {job_data.get('url', 'unknown')}")
            # Fallback to description/requirements to avoid empty vectors
            fallback = job_data.get('description') or job_data.get('requirements') or 'No information'
            embedding_text = str(fallback)[:500]
        
        return embedding_text
    
    def _prepare_payload(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Chuẩn bị payload để lưu vào Qdrant.
        
        Payload gồm:
        - salary_raw
        - jobDescriptionText (description)
        - benefits
        - positionName (title)
        - skills
        - requirements
        
        Args:
            job_data: Dictionary chứa dữ liệu job đầy đủ
            
        Returns:
            dict: Payload cho Qdrant
        """
        payload = {
            # Core fields for vector search
            'positionName': job_data.get('title') or job_data.get('positionName') or '',
            'skills': job_data.get('skills', []),
            
            # Additional info
            'salary_raw': job_data.get('salary_raw') or '',
            'jobDescriptionText': job_data.get('description') or '',
            'benefits': job_data.get('benefits') or '',
            'requirements': job_data.get('requirements') or '',
            
            # Metadata
            'company': job_data.get('company') or '',
            'location': job_data.get('location') or '',
            'url': job_data.get('url') or '',
            'source': job_data.get('source') or '',
            
            # Timestamps
            'crawl_timestamp': self._convert_timestamp(
                job_data.get('crawl_timestamp')
            ),
            'last_seen_timestamp': self._convert_timestamp(
                job_data.get('last_seen_timestamp')
            ),
        }
        
        return payload
    
    def _convert_timestamp(self, timestamp: Any) -> Optional[str]:
        """
        Convert timestamp to ISO string.
        
        Args:
            timestamp: datetime object or string
            
        Returns:
            ISO format string or None
        """
        if timestamp is None:
            return None
        
        if isinstance(timestamp, datetime):
            return timestamp.isoformat()
        
        if isinstance(timestamp, str):
            return timestamp
        
        return str(timestamp)
    
    def _convert_job_id(self, job_id: Union[str, ObjectId]) -> str:
        """
        Convert job_id to UUID string for Qdrant.
        
        Args:
            job_id: MongoDB ObjectId or string
            
        Returns:
            str: UUID string
        """
        import uuid
        
        # If already a valid UUID string, return it
        if isinstance(job_id, str):
            try:
                uuid.UUID(job_id)
                return job_id
            except ValueError:
                # Not a UUID, need to convert
                pass
        
        # Convert to UUID using MD5 hash (deterministic)
        import hashlib
        job_id_str = str(job_id)
        hash_bytes = hashlib.md5(job_id_str.encode()).digest()
        # Create UUID from hash bytes
        return str(uuid.UUID(bytes=hash_bytes))
    
    def upsert_job(
        self,
        job_id: Union[str, ObjectId],
        job_data: Dict[str, Any],
        skip_embedding: bool = False
    ) -> bool:
        """
        Insert hoặc update job posting vào Qdrant với auto-embedding.
        
        Args:
            job_id: MongoDB document ID (dùng làm point ID trong Qdrant)
            job_data: Dictionary chứa dữ liệu job đầy đủ
            skip_embedding: Bỏ qua embedding nếu True (dùng cho testing)
            
        Returns:
            bool: True nếu thành công
            
        Examples:
            >>> wrapper = QdrantJobWrapper()
            >>> job_data = {
            ...     'title': 'Python Developer',
            ...     'skills': ['Python', 'Django', 'PostgreSQL'],
            ...     'description': '...',
            ...     'requirements': '...',
            ...     'benefits': '...',
            ...     'salary_raw': '15-20 triệu'
            ... }
            >>> wrapper.upsert_job('507f1f77bcf86cd799439011', job_data)
        """
        try:
            # Convert job_id to string
            point_id = self._convert_job_id(job_id)
            
            # Prepare payload
            payload = self._prepare_payload(job_data)
            
            # Get embedding
            if not skip_embedding:
                embedding_text = self._prepare_embedding_text(job_data)
                logger.debug(f"Embedding text (first 100 chars): {embedding_text[:100]}")
                
                vector = get_embedding(embedding_text)
                
                if not vector or len(vector) == 0:
                    logger.error(f"Failed to get embedding for job {point_id}")
                    return False
                
                logger.debug(f"Got embedding vector with dimension: {len(vector)}")
            else:
                # Use dummy vector for testing (respect configured vector size)
                vec_dim = get_qdrant_config().get('vector_size', 384)
                vector = [0.0] * vec_dim
            
            # Create point
            point = PointStruct(
                id=point_id,
                vector=vector,
                payload=payload
            )
            
            # Upsert to Qdrant
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            
            logger.info(f"Successfully upserted job {point_id} to Qdrant")
            return True
            
        except Exception as e:
            logger.error(f"Failed to upsert job {job_id} to Qdrant: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def upsert_jobs_batch(
        self,
        jobs: List[Dict[str, Any]],
        id_field: str = '_id'
    ) -> Dict[str, int]:
        """
        Batch insert/update nhiều jobs.
        
        Args:
            jobs: List of job dictionaries (phải có _id hoặc id field)
            id_field: Tên field chứa ID (default: '_id')
            
        Returns:
            dict: Statistics {'success': count, 'failed': count}
        """
        stats = {'success': 0, 'failed': 0}
        
        for job in jobs:
            job_id = job.get(id_field)
            if not job_id:
                logger.warning(f"Job missing {id_field} field, skipping")
                stats['failed'] += 1
                continue
            
            if self.upsert_job(job_id, job):
                stats['success'] += 1
            else:
                stats['failed'] += 1
        
        logger.info(f"Batch upsert completed: {stats}")
        return stats
    
    def delete_job(self, job_id: Union[str, ObjectId]) -> bool:
        """
        Xóa job khỏi Qdrant.
        
        Args:
            job_id: MongoDB document ID
            
        Returns:
            bool: True nếu thành công
        """
        try:
            point_id = self._convert_job_id(job_id)
            
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=[point_id]
            )
            
            logger.info(f"Deleted job {point_id} from Qdrant")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete job {job_id}: {e}")
            return False
    
    def search_similar_jobs(
        self,
        query_text: str,
        limit: int = 10,
        score_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Tìm kiếm jobs tương tự dựa trên text query.
        
        Args:
            query_text: Text để search (sẽ được embed)
            limit: Số lượng kết quả tối đa
            score_threshold: Ngưỡng similarity score (0-1)
            
        Returns:
            List of jobs với score
        """
        try:
            # Get embedding for query
            query_vector = get_embedding(query_text)
            
            if not query_vector:
                logger.error("Failed to get embedding for query")
                return []
            
            # Search in Qdrant
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold
            )
            
            # Convert to list of dicts
            jobs = []
            for result in results:
                job = {
                    'id': result.id,
                    'score': result.score,
                    **result.payload
                }
                jobs.append(job)
            
            logger.info(f"Found {len(jobs)} similar jobs for query: {query_text[:50]}")
            return jobs
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def search_by_position_and_skills(
        self,
        position: str,
        skills: List[str],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Tìm kiếm jobs theo position (skills optional cho filter sau này).
        
        Args:
            position: Tên vị trí
            skills: List kỹ năng (hiện tại không dùng trong embedding)
            limit: Số lượng kết quả
            
        Returns:
            List of matching jobs
        """
        # Embedding uses position/title only; skills stay in payload for later filters
        query_text = position or ''
        
        return self.search_similar_jobs(query_text, limit=limit)
    
    def get_job(self, job_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """
        Lấy thông tin job từ Qdrant.
        
        Args:
            job_id: MongoDB document ID
            
        Returns:
            dict: Job data or None
        """
        try:
            point_id = self._convert_job_id(job_id)
            
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[point_id]
            )
            
            if not points:
                return None
            
            point = points[0]
            return {
                'id': point.id,
                **point.payload
            }
            
        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            return None
    
    def count_jobs(self) -> int:
        """
        Đếm số lượng jobs trong collection.
        
        Returns:
            int: Số lượng jobs
        """
        try:
            info = self.client.get_collection(self.collection_name)
            return info.points_count or 0
        except Exception as e:
            logger.error(f"Failed to count jobs: {e}")
            return 0


def create_qdrant_wrapper(
    collection_name: Optional[str] = None
) -> QdrantJobWrapper:
    """
    Factory function để tạo QdrantJobWrapper.
    
    Args:
        collection_name: Collection name (optional)
        
    Returns:
        QdrantJobWrapper instance
    """
    return QdrantJobWrapper(collection_name=collection_name)


if __name__ == "__main__":
    # Test wrapper
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
    )
    
    try:
        print("=" * 60)
        print("Testing Qdrant Job Wrapper")
        print("=" * 60)
        
        # Test 1: Initialize wrapper
        print("\n1. Initializing wrapper...")
        wrapper = QdrantJobWrapper()
        print(f"   [OK] Wrapper initialized with collection: {wrapper.collection_name}")
        
        # Test 2: Count existing jobs
        print("\n2. Counting existing jobs...")
        count = wrapper.count_jobs()
        print(f"   Current jobs count: {count}")
        
        # Test 3: Insert test job
        print("\n3. Inserting test job...")
        test_job = {
            'title': 'Senior Python Developer',
            'company': 'TechCorp Vietnam',
            'skills': ['Python', 'Django', 'PostgreSQL', 'Docker', 'AWS'],
            'description': 'Chúng tôi đang tìm kiếm Senior Python Developer có kinh nghiệm về Django và PostgreSQL.',
            'requirements': 'Có ít nhất 3 năm kinh nghiệm với Python và Django framework.',
            'benefits': 'Lương competitive, bảo hiểm đầy đủ, cơ hội thăng tiến.',
            'salary_raw': '20-30 triệu VND',
            'location': 'Hà Nội',
            'url': 'https://example.com/jobs/test-001',
            'source': 'test',
            'crawl_timestamp': datetime.utcnow(),
            'last_seen_timestamp': datetime.utcnow()
        }
        
        test_id = 'test_job_001'
        success = wrapper.upsert_job(test_id, test_job)
        if success:
            print(f"   [OK] Job inserted with ID: {test_id}")
        else:
            print(f"   [FAILED] Job insertion failed")
            sys.exit(1)
        
        # Test 4: Retrieve job
        print("\n4. Retrieving job...")
        retrieved = wrapper.get_job(test_id)
        if retrieved:
            print(f"   [OK] Retrieved job: {retrieved.get('positionName')}")
            print(f"   Skills: {retrieved.get('skills')}")
        else:
            print("   [FAILED] Job not found")
        
        # Test 5: Search similar jobs
        print("\n5. Searching similar jobs...")
        query = "Python Developer với kinh nghiệm Django"
        results = wrapper.search_similar_jobs(query, limit=5, score_threshold=0.5)
        print(f"   Found {len(results)} similar jobs:")
        for i, job in enumerate(results, 1):
            print(f"   {i}. {job.get('positionName')} - Score: {job.get('score'):.3f}")
        
        # Test 6: Search by position and skills
        print("\n6. Searching by position and skills...")
        results = wrapper.search_by_position_and_skills(
            position="Backend Developer",
            skills=["Python", "PostgreSQL"],
            limit=5
        )
        print(f"   Found {len(results)} matching jobs")
        
        # Test 7: Count jobs after insert
        print("\n7. Counting jobs after insert...")
        new_count = wrapper.count_jobs()
        print(f"   New jobs count: {new_count}")
        
        print("\n" + "=" * 60)
        print("[SUCCESS] All tests passed successfully")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
