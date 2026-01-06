"""
Qdrant Connection Factory Module

Module này cung cấp factory pattern để tạo và quản lý kết nối tới Qdrant Vector Database.
Sử dụng Singleton pattern để đảm bảo chỉ có một connection duy nhất.

Usage:
    from config.qdrant_connections import get_qdrant_client, get_collection_name
    
    # Lấy Qdrant client
    client = get_qdrant_client()
    
    # Lấy collection name
    collection_name = get_collection_name()
    
    # Tạo collection nếu chưa tồn tại
    create_collection_if_not_exists()
"""

import os
import logging
from typing import Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import yaml


logger = logging.getLogger(__name__)


class QdrantConnectionFactory:
    """
    Singleton Factory class để quản lý Qdrant connections.
    
    Attributes:
        _instance: Singleton instance
        _client: Qdrant client instance
        _config: Configuration dictionary từ settings.yaml
    """
    
    _instance: Optional['QdrantConnectionFactory'] = None
    _client: Optional[QdrantClient] = None
    _config: Optional[dict] = None
    
    def __new__(cls):
        """Implement Singleton pattern"""
        if cls._instance is None:
            cls._instance = super(QdrantConnectionFactory, cls).__new__(cls)
            cls._instance._load_config()
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
                self._config = full_config.get('qdrant', {})
                
            logger.info("Qdrant configuration loaded successfully")
            
        except FileNotFoundError:
            logger.warning("settings.yaml not found, using default Qdrant configuration")
            self._config = self._get_default_config()
        except yaml.YAMLError as e:
            logger.error(f"Error parsing settings.yaml: {e}")
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> dict:
        """Trả về cấu hình mặc định nếu không load được từ file"""
        return {
            'host': 'localhost',
            'port': 6333,
            'collection_name': 'job_descriptions',
            'timeout': 5000,
            'prefer_grpc': False,
            'vector_size': 384,
            'distance': 'Cosine'
        }
    
    def get_client(self) -> QdrantClient:
        """
        Tạo hoặc trả về Qdrant client instance.
        
        Ưu tiên sử dụng biến môi trường nếu có,
        nếu không sẽ dùng giá trị từ settings.yaml.
        
        Returns:
            QdrantClient: Qdrant client instance
            
        Raises:
            Exception: Nếu không thể kết nối tới Qdrant
        """
        if self._client is None:
            try:
                # Ưu tiên lấy từ biến môi trường (cho Docker)
                host = os.getenv('QDRANT_HOST', self._config.get('host'))
                port = int(os.getenv('QDRANT_PORT', self._config.get('port', 6333)))
                timeout = self._config.get('timeout', 5000) / 1000  # Convert to seconds
                prefer_grpc = self._config.get('prefer_grpc', False)
                
                # Tạo Qdrant client
                self._client = QdrantClient(
                    host=host,
                    port=port,
                    timeout=timeout,
                    prefer_grpc=prefer_grpc
                )
                
                # Test connection
                self._client.get_collections()
                logger.info(f"Successfully connected to Qdrant at {host}:{port}")
                
            except Exception as e:
                logger.error(f"Failed to connect to Qdrant: {e}")
                raise
        
        return self._client
    
    def get_collection_name(self) -> str:
        """
        Trả về tên collection từ config hoặc biến môi trường.
        
        Returns:
            str: Tên collection
        """
        return os.getenv(
            'QDRANT_COLLECTION',
            self._config.get('collection_name', 'job_descriptions')
        )
    
    def collection_exists(self, collection_name: Optional[str] = None) -> bool:
        """
        Kiểm tra collection có tồn tại hay không.
        
        Args:
            collection_name: Tên collection. Nếu None, sử dụng giá trị từ config.
            
        Returns:
            bool: True nếu collection tồn tại
        """
        try:
            client = self.get_client()
            name = collection_name or self.get_collection_name()
            collections = client.get_collections().collections
            return any(col.name == name for col in collections)
        except Exception as e:
            logger.error(f"Error checking collection existence: {e}")
            return False
    
    def create_collection(
        self, 
        collection_name: Optional[str] = None,
        vector_size: Optional[int] = None,
        distance: Optional[str] = None
    ) -> None:
        """
        Tạo collection mới với cấu hình từ settings.yaml hoặc parameters.
        
        Args:
            collection_name: Tên collection (optional)
            vector_size: Kích thước vector (optional)
            distance: Loại distance metric: 'Cosine', 'Euclid', 'Dot' (optional)
            
        Raises:
            Exception: Nếu không thể tạo collection
        """
        try:
            client = self.get_client()
            name = collection_name or self.get_collection_name()
            vec_size = vector_size or int(self._config.get('vector_size', 768))
            distance_str = distance or self._config.get('distance', 'Cosine')
            
            # Map string distance to Distance enum
            distance_map = {
                'Cosine': Distance.COSINE,
                'Euclid': Distance.EUCLID,
                'Dot': Distance.DOT
            }
            distance_metric = distance_map.get(distance_str, Distance.COSINE)
            
            client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=vec_size,
                    distance=distance_metric
                )
            )
            logger.info(f"Created Qdrant collection: {name} (size={vec_size}, distance={distance_str})")
            
        except Exception as e:
            logger.error(f"Error creating Qdrant collection: {e}")
            raise
    
    def create_collection_if_not_exists(
        self, 
        collection_name: Optional[str] = None
    ) -> bool:
        """
        Tạo collection nếu chưa tồn tại.
        
        Args:
            collection_name: Tên collection (optional)
            
        Returns:
            bool: True nếu collection được tạo mới, False nếu đã tồn tại
        """
        name = collection_name or self.get_collection_name()
        
        if self.collection_exists(name):
            logger.info(f"Qdrant collection already exists: {name}")
            return False
        else:
            self.create_collection(name)
            return True
    
    def delete_collection(self, collection_name: Optional[str] = None) -> None:
        """
        Xóa collection.
        
        Args:
            collection_name: Tên collection (optional)
        """
        try:
            client = self.get_client()
            name = collection_name or self.get_collection_name()
            client.delete_collection(collection_name=name)
            logger.info(f"Deleted Qdrant collection: {name}")
        except Exception as e:
            logger.error(f"Error deleting collection: {e}")
            raise
    
    def get_collection_info(self, collection_name: Optional[str] = None) -> dict:
        """
        Lấy thông tin về collection.
        
        Args:
            collection_name: Tên collection (optional)
            
        Returns:
            dict: Thông tin collection
        """
        try:
            client = self.get_client()
            name = collection_name or self.get_collection_name()
            info = client.get_collection(collection_name=name)
            return {
                'name': name,
                'vectors_count': info.vectors_count,
                'points_count': info.points_count,
                'status': info.status,
                'config': info.config
            }
        except Exception as e:
            logger.error(f"Error getting collection info: {e}")
            raise
    
    def close(self) -> None:
        """Đóng Qdrant connection"""
        if self._client is not None:
            self._client.close()
            self._client = None
            logger.info("Qdrant connection closed")
    
    def get_config(self) -> dict:
        """Trả về configuration dictionary"""
        return self._config.copy()


# Global factory instance
_qdrant_factory = QdrantConnectionFactory()


# Convenience functions để sử dụng trực tiếp
def get_qdrant_client() -> QdrantClient:
    """
    Lấy Qdrant client instance.
    
    Returns:
        QdrantClient: Qdrant client
        
    Examples:
        >>> client = get_qdrant_client()
        >>> collections = client.get_collections()
    """
    return _qdrant_factory.get_client()


def get_collection_name() -> str:
    """
    Lấy tên collection Qdrant từ config.
    
    Returns:
        str: Tên collection
        
    Examples:
        >>> collection_name = get_collection_name()
        >>> print(collection_name)  # 'job_descriptions'
    """
    return _qdrant_factory.get_collection_name()


def collection_exists(collection_name: Optional[str] = None) -> bool:
    """
    Kiểm tra collection có tồn tại hay không.
    
    Args:
        collection_name: Tên collection (optional)
        
    Returns:
        bool: True nếu collection tồn tại
    """
    return _qdrant_factory.collection_exists(collection_name)


def create_collection(
    collection_name: Optional[str] = None,
    vector_size: Optional[int] = None,
    distance: Optional[str] = None
) -> None:
    """
    Tạo collection mới.
    
    Args:
        collection_name: Tên collection (optional)
        vector_size: Kích thước vector (optional)
        distance: Loại distance metric (optional)
        
    Examples:
        >>> create_collection('my_collection', vector_size=384, distance='Cosine')
    """
    _qdrant_factory.create_collection(collection_name, vector_size, distance)


def create_collection_if_not_exists(collection_name: Optional[str] = None) -> bool:
    """
    Tạo collection nếu chưa tồn tại.
    
    Args:
        collection_name: Tên collection (optional)
        
    Returns:
        bool: True nếu collection được tạo mới
        
    Examples:
        >>> created = create_collection_if_not_exists()
        >>> if created:
        >>>     print("Collection created")
    """
    return _qdrant_factory.create_collection_if_not_exists(collection_name)


def delete_collection(collection_name: Optional[str] = None) -> None:
    """
    Xóa collection.
    
    Args:
        collection_name: Tên collection (optional)
    """
    _qdrant_factory.delete_collection(collection_name)


def get_collection_info(collection_name: Optional[str] = None) -> dict:
    """
    Lấy thông tin về collection.
    
    Args:
        collection_name: Tên collection (optional)
        
    Returns:
        dict: Thông tin collection
        
    Examples:
        >>> info = get_collection_info()
        >>> print(f"Points count: {info['points_count']}")
    """
    return _qdrant_factory.get_collection_info(collection_name)


def close_connection() -> None:
    """Đóng Qdrant connection"""
    _qdrant_factory.close()


def get_config() -> dict:
    """
    Lấy Qdrant configuration.
    
    Returns:
        dict: Configuration dictionary
    """
    return _qdrant_factory.get_config()


if __name__ == "__main__":
    # Test connection
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
    )
    
    try:
        print("=" * 60)
        print("Testing Qdrant Connection")
        print("=" * 60)
        
        # Test 1: Get client
        print("\n1. Testing connection...")
        client = get_qdrant_client()
        print("   [OK] Connected successfully")
        
        # Test 2: Get config
        print("\n2. Getting configuration...")
        config = get_config()
        for key, value in config.items():
            print(f"   {key}: {value}")
        
        # Test 3: Get collection name
        print("\n3. Getting collection name...")
        collection_name = get_collection_name()
        print(f"   Collection: {collection_name}")
        
        # Test 4: Check if collection exists
        print("\n4. Checking collection existence...")
        exists = collection_exists()
        print(f"   Collection exists: {exists}")
        
        # Test 5: Create collection if not exists
        if not exists:
            print("\n5. Creating collection...")
            created = create_collection_if_not_exists()
            if created:
                print("   [OK] Collection created successfully")
        else:
            print("\n5. Getting collection info...")
            info = get_collection_info()
            print(f"   Vectors count: {info.get('vectors_count', 0)}")
            print(f"   Points count: {info.get('points_count', 0)}")
            print(f"   Status: {info.get('status', 'unknown')}")
        
        # Test 6: Close connection
        print("\n6. Closing connection...")
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
