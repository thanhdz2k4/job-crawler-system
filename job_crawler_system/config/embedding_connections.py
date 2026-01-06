"""
Embedding Service Connection Module

Module này cung cấp factory pattern để tạo và quản lý kết nối tới Embedding Service.
Sử dụng Singleton pattern để đảm bảo chỉ có một connection duy nhất.

Usage:
    from config.embedding_connections import get_embedding, get_embeddings_batch
    
    # Embed một đoạn text
    embedding = get_embedding("Tuyển dụng lập trình viên Python")
    
    # Embed nhiều đoạn text
    texts = ["Text 1", "Text 2", "Text 3"]
    embeddings = get_embeddings_batch(texts)
"""

import os
import logging
from typing import Optional, List, Dict, Any
import requests
import yaml
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


logger = logging.getLogger(__name__)


class EmbeddingServiceFactory:
    """
    Singleton Factory class để quản lý Embedding Service connections.
    
    Attributes:
        _instance: Singleton instance
        _session: Requests session với connection pooling
        _config: Configuration dictionary từ settings.yaml
    """
    
    _instance: Optional['EmbeddingServiceFactory'] = None
    _session: Optional[requests.Session] = None
    _config: Optional[dict] = None
    
    def __new__(cls):
        """Implement Singleton pattern"""
        if cls._instance is None:
            cls._instance = super(EmbeddingServiceFactory, cls).__new__(cls)
            cls._instance._load_config()
            cls._instance._setup_session()
        return cls._instance
    
    def _load_config(self) -> None:
        """Load configuration từ settings.yaml"""
        try:
            config_path = os.path.join(
                os.path.dirname(__file__),
                'settings.yaml'
            )
            
            with open(config_path, 'r', encoding='utf-8') as f:
                full_config = yaml.safe_load(f)
                self._config = full_config.get('embedding', {})
                
            logger.info("Embedding service configuration loaded successfully")
            
        except FileNotFoundError:
            logger.warning("settings.yaml not found, using default embedding configuration")
            self._config = self._get_default_config()
        except yaml.YAMLError as e:
            logger.error(f"Error parsing settings.yaml: {e}")
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> dict:
        """Trả về cấu hình mặc định nếu không load được từ file"""
        return {
            'base_url': 'http://localhost:31113',
            'embed_path': '/embed',
            'model': 'dangvantuan/vietnamese-embedding',
            'dimension': 384,
            'timeout': 30000,
            'max_retries': 3,
            'batch_size': 32
        }
    
    def _setup_session(self) -> None:
        """Setup requests session với retry và connection pooling"""
        self._session = requests.Session()
        
        # Configure retry strategy
        max_retries = self._config.get('max_retries', 3)
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"]
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20
        )
        
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)
        
        # Set default headers
        self._session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def get_base_url(self) -> str:
        """
        Lấy base URL từ config hoặc biến môi trường.
        
        Returns:
            str: Base URL của embedding service
        """
        return os.getenv(
            'EMBEDDING_BASE_URL',
            self._config.get('base_url', 'http://localhost:31113')
        )
    
    def get_embed_url(self) -> str:
        """
        Lấy full URL cho embed endpoint.
        
        Returns:
            str: Full URL cho embedding
        """
        base_url = self.get_base_url()
        embed_path = self._config.get('embed_path', '/embed')
        return f"{base_url.rstrip('/')}{embed_path}"
    
    def embed_text(self, text: str) -> Dict[str, Any]:
        """
        Embed một đoạn text thành vector.
        
        Args:
            text: Text cần embedding
            
        Returns:
            dict: Response từ embedding service chứa:
                - embeddings: List of float values
                - dimension: Vector dimension (768)
                - model: Model name
                
        Raises:
            requests.exceptions.RequestException: Nếu request thất bại
            ValueError: Nếu response không hợp lệ
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        url = self.get_embed_url()
        timeout = self._config.get('timeout', 30000) / 1000  # Convert to seconds
        
        payload = {"text": text.strip()}
        
        try:
            logger.debug(f"Embedding text (length: {len(text)})")
            
            response = self._session.post(
                url,
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Validate response structure
            if 'embeddings' not in data:
                raise ValueError("Invalid response: missing 'embeddings' field")
            
            if 'dimension' not in data:
                logger.warning("Response missing 'dimension' field")
                data['dimension'] = len(data['embeddings'])
            
            if 'model' not in data:
                logger.warning("Response missing 'model' field")
                data['model'] = self._config.get('model', 'unknown')
            
            logger.debug(f"Successfully embedded text, dimension: {data['dimension']}")
            return data
            
        except requests.exceptions.Timeout:
            logger.error(f"Embedding request timeout after {timeout}s")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Embedding request failed: {e}")
            raise
        except ValueError as e:
            logger.error(f"Invalid response from embedding service: {e}")
            raise
    
    def embed_texts_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        """
        Embed nhiều đoạn text (batch processing).
        
        Args:
            texts: List of texts cần embedding
            
        Returns:
            List[dict]: List of embedding responses
            
        Note:
            Tự động chia nhỏ theo batch_size nếu cần
        """
        if not texts:
            return []
        
        batch_size = self._config.get('batch_size', 32)
        results = []
        
        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}")
            
            for text in batch:
                try:
                    result = self.embed_text(text)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to embed text in batch: {e}")
                    # Add None or empty result to maintain alignment
                    results.append({
                        'embeddings': [],
                        'dimension': 0,
                        'model': 'error',
                        'error': str(e)
                    })
        
        return results
    
    def get_embedding_vector(self, text: str) -> List[float]:
        """
        Lấy vector embedding trực tiếp (chỉ trả về list of floats).
        
        Args:
            text: Text cần embedding
            
        Returns:
            List[float]: Vector embedding
        """
        response = self.embed_text(text)
        return response.get('embeddings', [])
    
    def get_embeddings_vectors_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Lấy vectors embedding cho nhiều texts.
        
        Args:
            texts: List of texts
            
        Returns:
            List[List[float]]: List of embedding vectors
        """
        responses = self.embed_texts_batch(texts)
        return [resp.get('embeddings', []) for resp in responses]
    
    def test_connection(self) -> bool:
        """
        Test kết nối tới embedding service.
        
        Returns:
            bool: True nếu kết nối thành công
        """
        try:
            test_text = "Test connection"
            response = self.embed_text(test_text)
            
            if response.get('embeddings') and len(response['embeddings']) > 0:
                logger.info("Embedding service connection test successful")
                return True
            else:
                logger.warning("Embedding service returned empty embeddings")
                return False
                
        except Exception as e:
            logger.error(f"Embedding service connection test failed: {e}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Lấy thông tin về model đang sử dụng.
        
        Returns:
            dict: Model information
        """
        return {
            'model': self._config.get('model'),
            'dimension': self._config.get('dimension'),
            'base_url': self.get_base_url(),
            'embed_url': self.get_embed_url()
        }
    
    def close(self) -> None:
        """Đóng session"""
        if self._session is not None:
            self._session.close()
            self._session = None
            logger.info("Embedding service session closed")
    
    def get_config(self) -> dict:
        """Trả về configuration dictionary"""
        return self._config.copy()


# Global factory instance
_embedding_factory = EmbeddingServiceFactory()


# Convenience functions để sử dụng trực tiếp
def get_embedding(text: str) -> List[float]:
    """
    Embed một đoạn text và trả về vector.
    
    Args:
        text: Text cần embedding
        
    Returns:
        List[float]: Embedding vector
        
    Examples:
        >>> vector = get_embedding("Tuyển dụng lập trình viên Python")
        >>> print(len(vector))  # 768
    """
    return _embedding_factory.get_embedding_vector(text)


def get_embedding_full(text: str) -> Dict[str, Any]:
    """
    Embed một đoạn text và trả về full response.
    
    Args:
        text: Text cần embedding
        
    Returns:
        dict: Full response with embeddings, dimension, model
        
    Examples:
        >>> response = get_embedding_full("Tuyển dụng lập trình viên")
        >>> print(response['dimension'])  # 768
        >>> print(response['model'])  # dangvantuan/vietnamese-embedding
    """
    return _embedding_factory.embed_text(text)


def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Embed nhiều đoạn text.
    
    Args:
        texts: List of texts
        
    Returns:
        List[List[float]]: List of embedding vectors
        
    Examples:
        >>> texts = ["Text 1", "Text 2", "Text 3"]
        >>> vectors = get_embeddings_batch(texts)
        >>> print(len(vectors))  # 3
    """
    return _embedding_factory.get_embeddings_vectors_batch(texts)


def get_embeddings_batch_full(texts: List[str]) -> List[Dict[str, Any]]:
    """
    Embed nhiều đoạn text và trả về full responses.
    
    Args:
        texts: List of texts
        
    Returns:
        List[dict]: List of full responses
    """
    return _embedding_factory.embed_texts_batch(texts)


def test_connection() -> bool:
    """
    Test kết nối tới embedding service.
    
    Returns:
        bool: True nếu kết nối thành công
    """
    return _embedding_factory.test_connection()


def get_model_info() -> Dict[str, Any]:
    """
    Lấy thông tin về model.
    
    Returns:
        dict: Model information
    """
    return _embedding_factory.get_model_info()


def close_connection() -> None:
    """Đóng connection"""
    _embedding_factory.close()


def get_config() -> dict:
    """Lấy embedding configuration"""
    return _embedding_factory.get_config()


if __name__ == "__main__":
    # Test embedding service
    import sys
    import json
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
    )
    
    try:
        print("=" * 60)
        print("Testing Embedding Service Connection")
        print("=" * 60)
        
        # Test 1: Get config
        print("\n1. Getting configuration...")
        config = get_config()
        for key, value in config.items():
            print(f"   {key}: {value}")
        
        # Test 2: Get model info
        print("\n2. Getting model information...")
        model_info = get_model_info()
        for key, value in model_info.items():
            print(f"   {key}: {value}")
        
        # Test 3: Test connection
        print("\n3. Testing connection...")
        if test_connection():
            print("   [OK] Connection successful")
        else:
            print("   [FAILED] Connection failed")
            sys.exit(1)
        
        # Test 4: Embed single text
        print("\n4. Testing single text embedding...")
        test_text = "Tuyển dụng lập trình viên Python với kinh nghiệm 2 năm"
        vector = get_embedding(test_text)
        print(f"   Text: {test_text}")
        print(f"   Vector dimension: {len(vector)}")
        print(f"   First 5 values: {vector[:5]}")
        
        # Test 5: Embed batch
        print("\n5. Testing batch embedding...")
        test_texts = [
            "Tuyển dụng Senior Backend Developer",
            "Cần tìm Frontend Developer biết React",
            "Tuyển DevOps Engineer có kinh nghiệm AWS"
        ]
        vectors = get_embeddings_batch(test_texts)
        print(f"   Number of texts: {len(test_texts)}")
        print(f"   Number of vectors: {len(vectors)}")
        for i, (text, vec) in enumerate(zip(test_texts, vectors), 1):
            print(f"   {i}. {text[:50]}... -> dimension: {len(vec)}")
        
        # Test 6: Get full response
        print("\n6. Testing full response...")
        full_response = get_embedding_full(test_texts[0])
        print(f"   Model: {full_response.get('model')}")
        print(f"   Dimension: {full_response.get('dimension')}")
        print(f"   Embeddings length: {len(full_response.get('embeddings', []))}")
        
        # Test 7: Close connection
        print("\n7. Closing connection...")
        close_connection()
        print("   [OK] Connection closed")
        
        print("\n" + "=" * 60)
        print("[SUCCESS] All tests passed successfully")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
