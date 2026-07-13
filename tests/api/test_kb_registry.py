"""kb_registry 模块测试"""

import json
import os
import tempfile
from pathlib import Path

from server.kb_registry import KBRegistry


def _create_registry(tmp_dir: str) -> KBRegistry:
    return KBRegistry(storage_path=Path(tmp_dir) / "kb_registry.json")


class TestKBRegistry:
    """知识库目录管理单元测试"""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.registry = _create_registry(self.tmp_dir)
        self.registry_path = Path(self.tmp_dir) / "kb_registry.json"

    def teardown_method(self):
        if self.registry_path.exists():
            os.remove(self.registry_path)
        os.rmdir(self.tmp_dir)

    def test_init_creates_empty_registry(self):
        """初始化时 registry 不存在则自动创建空列表"""
        assert self.registry_path.exists()
        data = json.loads(self.registry_path.read_text(encoding="utf-8"))
        assert data == []

    def test_create_kb(self):
        """创建知识库后 registry 包含该项"""
        result = self.registry.create_kb(kb_id="my-docs", kb_name="我的文档")
        assert result["kb_id"] == "my-docs"
        assert result["kb_name"] == "我的文档"
        assert "created_at" in result
        assert result["doc_count"] == 0
        assert result["status"] == "active"

    def test_create_duplicate_kb_id_raises(self):
        """重复 kb_id 抛异常"""
        self.registry.create_kb(kb_id="my-docs", kb_name="我的文档")
        import pytest
        with pytest.raises(ValueError, match="已存在"):
            self.registry.create_kb(kb_id="my-docs", kb_name="另一个文档")

    def test_list_kbs(self):
        """列出所有知识库"""
        self.registry.create_kb(kb_id="kb1", kb_name="库1")
        self.registry.create_kb(kb_id="kb2", kb_name="库2")
        result = self.registry.list_kbs()
        assert len(result) == 2
        ids = [k["kb_id"] for k in result]
        assert "kb1" in ids
        assert "kb2" in ids

    def test_get_kb(self):
        """按 kb_id 获取知识库"""
        self.registry.create_kb(kb_id="my-docs", kb_name="我的文档")
        result = self.registry.get_kb("my-docs")
        assert result is not None
        assert result["kb_name"] == "我的文档"

    def test_get_nonexistent_kb_returns_none(self):
        """不存在的 kb_id 返回 None"""
        result = self.registry.get_kb("nonexistent")
        assert result is None

    def test_update_kb_name(self):
        """更新知识库名称"""
        self.registry.create_kb(kb_id="my-docs", kb_name="我的文档")
        result = self.registry.update_kb(kb_id="my-docs", kb_name="新产品文档")
        assert result["kb_name"] == "新产品文档"
        assert "updated_at" in result

    def test_update_nonexistent_kb_raises(self):
        """更新不存在的知识库抛异常"""
        import pytest
        with pytest.raises(ValueError, match="不存在"):
            self.registry.update_kb(kb_id="nonexistent", kb_name="新名称")

    def test_delete_kb(self):
        """删除知识库"""
        self.registry.create_kb(kb_id="my-docs", kb_name="我的文档")
        result = self.registry.delete_kb("my-docs")
        assert result is True
        assert self.registry.get_kb("my-docs") is None

    def test_delete_nonexistent_kb_raises(self):
        """删除不存在的知识库抛异常"""
        import pytest
        with pytest.raises(ValueError, match="不存在"):
            self.registry.delete_kb("nonexistent")

    def test_exists(self):
        """检查知识库是否存在"""
        self.registry.create_kb(kb_id="my-docs", kb_name="我的文档")
        assert self.registry.exists("my-docs") is True
        assert self.registry.exists("nonexistent") is False

    def test_persistence_across_reload(self):
        """数据在多次加载间持久化"""
        self.registry.create_kb(kb_id="my-docs", kb_name="我的文档")
        registry2 = _create_registry(self.tmp_dir)
        result = registry2.list_kbs()
        assert len(result) == 1
        assert result[0]["kb_id"] == "my-docs"

    def test_empty_registry_after_clear(self):
        """清空 registry"""
        self.registry.create_kb(kb_id="kb1", kb_name="库1")
        self.registry.create_kb(kb_id="kb2", kb_name="库2")
        # 删除所有 KB
        self.registry.delete_kb("kb1")
        self.registry.delete_kb("kb2")
        result = self.registry.list_kbs()
        assert result == []
