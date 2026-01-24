"""
Memory Search Repositories

Export all memory search repositories (Elasticsearch and Milvus)
"""

# Try to import ES repository, but don't fail if elasticsearch is not installed
try:
    from infra_layer.adapters.out.search.repository.episodic_memory_es_repository import (
        EpisodicMemoryEsRepository,
    )
    _ES_AVAILABLE = True
except ImportError as e:
    import warnings
    warnings.warn(f"Elasticsearch repository not available: {e}")
    EpisodicMemoryEsRepository = None
    _ES_AVAILABLE = False

# Milvus repositories should always be available
from infra_layer.adapters.out.search.repository.episodic_memory_milvus_repository import (
    EpisodicMemoryMilvusRepository,
)
from infra_layer.adapters.out.search.repository.foresight_milvus_repository import (
    ForesightMilvusRepository,
)
from infra_layer.adapters.out.search.repository.event_log_milvus_repository import (
    EventLogMilvusRepository,
)

# Build __all__ dynamically based on what's available
__all__ = [
    "EpisodicMemoryMilvusRepository",
    "ForesightMilvusRepository",
    "EventLogMilvusRepository",
]

if _ES_AVAILABLE:
    __all__.append("EpisodicMemoryEsRepository")
