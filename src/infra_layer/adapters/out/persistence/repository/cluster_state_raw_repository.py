"""
ClusterState 原生 CRUD 仓库

基于 Beanie ODM 的聚类状态数据访问层，提供完整的 CRUD 操作。
"""

from typing import Optional, Dict, Any
from core.observation.logger import get_logger
from core.di.decorators import repository
from core.oxm.mongo.base_repository import BaseRepository

from infra_layer.adapters.out.persistence.document.memory.cluster_state import ClusterState

logger = get_logger(__name__)


@repository("cluster_state_raw_repository", primary=True)
class ClusterStateRawRepository(BaseRepository[ClusterState]):
    """
    ClusterState 原生 CRUD 仓库
    
    提供对 ClusterState 文档的直接数据库操作
    """
    
    def __init__(self):
        """初始化仓库"""
        super().__init__(ClusterState)
    
    async def get_by_group_id(self, group_id: str) -> Optional[ClusterState]:
        """
        根据 group_id 获取聚类状态
        
        Args:
            group_id: 群组ID
            
        Returns:
            ClusterState 实例或 None
        """
        try:
            result = await self.model.find_one(ClusterState.group_id == group_id)
            return result
        except Exception as e:
            logger.error(f"获取聚类状态失败: group_id={group_id}, error={e}")
            return None
    
    async def upsert_by_group_id(
        self,
        group_id: str,
        state: Dict[str, Any]
    ) -> Optional[ClusterState]:
        """
        根据 group_id 更新或插入聚类状态
        
        Args:
            group_id: 群组ID
            state: 聚类状态字典
            
        Returns:
            更新后的 ClusterState 实例或 None
        """
        try:
            existing = await self.model.find_one(ClusterState.group_id == group_id)
            
            if existing:
                # 更新现有文档
                for key, value in state.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
                await existing.save()
                logger.debug(f"更新聚类状态: group_id={group_id}")
                return existing
            else:
                # 创建新文档
                state["group_id"] = group_id
                cluster_state = ClusterState(**state)
                await cluster_state.insert()
                logger.info(f"创建聚类状态: group_id={group_id}")
                return cluster_state
        
        except Exception as e:
            logger.error(f"保存聚类状态失败: group_id={group_id}, error={e}")
            return None
    
    async def get_cluster_assignments(self, group_id: str) -> Dict[str, str]:
        """
        获取群组的 event_id -> cluster_id 映射
        
        Args:
            group_id: 群组ID
            
        Returns:
            事件到聚类的映射字典
        """
        try:
            cluster_state = await self.model.find_one(ClusterState.group_id == group_id)
            if cluster_state is None:
                return {}
            return cluster_state.eventid_to_cluster or {}
        except Exception as e:
            logger.error(f"获取聚类映射失败: group_id={group_id}, error={e}")
            return {}
    
    async def delete_by_group_id(self, group_id: str) -> bool:
        """
        删除指定群组的聚类状态
        
        Args:
            group_id: 群组ID
            
        Returns:
            是否删除成功
        """
        try:
            cluster_state = await self.model.find_one(ClusterState.group_id == group_id)
            if cluster_state:
                await cluster_state.delete()
                logger.info(f"删除聚类状态: group_id={group_id}")
            return True
        except Exception as e:
            logger.error(f"删除聚类状态失败: group_id={group_id}, error={e}")
            return False
    
    async def delete_all(self) -> int:
        """
        删除所有聚类状态
        
        Returns:
            删除的文档数量
        """
        try:
            result = await self.model.delete_all()
            count = result.deleted_count if result else 0
            logger.info(f"删除所有聚类状态: {count} 条")
            return count
        except Exception as e:
            logger.error(f"删除所有聚类状态失败: {e}")
            return 0

