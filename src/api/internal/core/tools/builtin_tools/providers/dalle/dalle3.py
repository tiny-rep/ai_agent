from langchain_community.tools.openai_dalle_image_generation import OpenAIDALLEImageGenerationTool
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from internal.lib.helper import add_attribute


class Dalle3ArgSchema(BaseModel):
    query: str = Field(description="输入需要生成图像的文本提示{prompt}")


@add_attribute("args_schema", Dalle3ArgSchema)
def dalle3(**kwargs) -> BaseTool:
    return OpenAIDALLEImageGenerationTool(
        api_wrapper=DallEAPIWrapper(model="dall-e-3", **kwargs),
        args_schema=Dalle3ArgSchema
    )
