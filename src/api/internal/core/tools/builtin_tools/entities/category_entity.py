from pydantic import BaseModel, field_validator

from internal.exception import FailException


class CategoryEntity(BaseModel):
    category: str  # 唯一性标识
    name: str  # 分类名字
    icon: str  # 分类Icon图标

    @field_validator("icon")
    def check_icon_extension(cls, value: str):
        if not value.endswith(".svg"):
            raise FailException("分类的icon图标不是.svg格式")
        return value
