"""MongoDB-based cluster storage for ClusterManager."""

from typing import Any, Dict, Optional

from memory_layer.cluster_manager.storage import ClusterStorage
from core.observation.logger import get_logger
from core.di.decorators import component
from core.di import get_bean_by_type
from infra_layer.adapters.out.persistence.repository.cluster_state_raw_repository import (
    ClusterStateRawRepository,
)

logger = get_logger(__name__)


@component()
class MongoClusterStorage(ClusterStorage):
    """MongoDB-based cluster storage implementation.
    
    使用 ClusterStateRawRepository 进行数据库操作。
    """
    
    def __init__(self):
        """初始化 MongoDB 聚类存储"""
        logger.info("MongoClusterStorage initialized")
    
    def _get_repo(self) -> ClusterStateRawRepository:
        """获取 repository 实例"""
        return get_bean_by_type(ClusterStateRawRepository)
    
    async def save_cluster_state(
        self,
        group_id: str,
        state: Dict[str, Any]
    ) -> bool:
        """保存群组的聚类状态"""
        result = await self._get_repo().upsert_by_group_id(group_id, state)
        return result is not None
    
    async def load_cluster_state(
        self,
        group_id: str
    ) -> Optional[Dict[str, Any]]:
        """加载群组的聚类状态"""
        cluster_state = await self._get_repo().get_by_group_id(group_id)
        if cluster_state is None:
            return None
        # 转换为字典（排除 MongoDB 内部字段）
        return cluster_state.model_dump(exclude={"id", "revision_id"})
    
    async def get_cluster_assignments(
        self,
        group_id: str
    ) -> Dict[str, str]:
        """获取群组的 event_id -> cluster_id 映射"""
        return await self._get_repo().get_cluster_assignments(group_id)
    
    async def clear(self, group_id: Optional[str] = None) -> bool:
        """清除聚类状态"""
        repo = self._get_repo()
        if group_id is None:
            await repo.delete_all()
        else:
            await repo.delete_by_group_id(group_id)
        return True
