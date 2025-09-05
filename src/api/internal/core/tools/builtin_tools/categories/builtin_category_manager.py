import os.path
from typing import Any

import yaml
from injector import inject, singleton
from pydantic import BaseModel, Field

from internal.core.tools.builtin_tools.entities.category_entity import CategoryEntity
from internal.exception import NotFoundException


@inject
@singleton
class BuiltinCategoryManager(BaseModel):
    """内置工具分类管理器"""
    category_map: dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_categories()

    def get_category_map(self) -> dict[str, Any]:
        """获取所有分类数据"""
        return self.category_map

    def _init_categories(self):
        """初始化数据"""
        # 1.查看是否存在缓存，存在则直接返回
        if self.category_map:
            return
        # 2.获取yaml文件的数据，然后做相就的解析
        current_path = os.path.abspath(__file__)
        category_path = os.path.dirname(current_path)
        category_yaml_path = os.path.join(category_path, "categories.yaml")
        with open(category_yaml_path, encoding="utf-8") as f:
            categories = yaml.safe_load(f)

        # 3.循环Yaml文件内容
        for category in categories:
            # 4.创建分类实体
            category_entity = CategoryEntity(**category)
            # 5.获取Icon的位置
            icon_path = os.path.join(category_path, "icons", category_entity.icon)
            if not os.path.exists(icon_path):
                raise NotFoundException(f"分类{category_entity.category}的icon未提供")
            # 6.读取Icon的数据
            with open(icon_path, encoding="utf-8") as f:
                icon = f.read()
            # 7.将数据映射到字典中
            self.category_map[category_entity.category] = {
                "entity": category_entity,
                "icon": icon
            }
