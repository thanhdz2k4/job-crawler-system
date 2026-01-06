#!/usr/bin/env python3
"""
Script to recreate Qdrant collection with correct vector dimension.

This script will:
1. Delete the existing collection (if it exists)
2. Create a new collection with dimension 384
3. Verify the collection is created successfully

Usage:
    python scripts/recreate_qdrant_collection.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.qdrant_connections import (
    collection_exists,
    get_collection_name,
    delete_collection,
    create_collection,
    get_collection_info,
    get_config
)
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main execution function"""
    try:
        collection_name = get_collection_name()
        config = get_config()
        
        logger.info(f"Target collection: {collection_name}")
        logger.info(f"Qdrant host: {config.get('host')}:{config.get('port')}")
        
        # Check if collection exists
        if collection_exists(collection_name):
            logger.warning(f"Collection '{collection_name}' already exists")
            
            # Get collection info
            try:
                info = get_collection_info(collection_name)
                config_obj = info.get('config')
                if config_obj:
                    current_dim = config_obj.params.vectors.size
                    logger.info(f"Current vector dimension: {current_dim}")
                    
                    if current_dim == 384:
                        logger.info("Collection already has correct dimension (384). No action needed.")
                        return
                    
                    logger.warning(f"Collection has wrong dimension ({current_dim}), need to recreate with 384")
            except Exception as e:
                logger.error(f"Error getting collection info: {e}")
            
            # Delete existing collection (auto-confirm in script)
            logger.info(f"Deleting collection '{collection_name}'...")
            delete_collection(collection_name)
            logger.info("Collection deleted successfully")
        
        # Create new collection with dimension 384
        logger.info("Creating new collection with dimension 384...")
        create_collection(
            collection_name=collection_name,
            vector_size=384,
            distance='Cosine'
        )
        logger.info(f"Collection '{collection_name}' created successfully")
        
        # Verify collection
        info = get_collection_info(collection_name)
        # info is a dict with 'config' key containing a CollectionConfig object
        config_obj = info.get('config')
        if config_obj:
            vector_dim = config_obj.params.vectors.size
            logger.info(f"Verified: Collection created with dimension {vector_dim}")
            
            if vector_dim == 384:
                logger.info("✓ Collection setup complete!")
            else:
                logger.error(f"✗ Unexpected dimension: {vector_dim} (expected 384)")
        else:
            logger.warning("Could not verify collection dimension")
            
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
