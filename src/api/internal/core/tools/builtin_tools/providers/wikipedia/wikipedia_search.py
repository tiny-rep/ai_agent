from langchain_community.tools.wikipedia.tool import WikipediaQueryRun, WikipediaQueryInput
from langchain_core.tools import BaseTool

from internal.lib.helper import add_attribute


@add_attribute("args_schema", WikipediaQueryInput)
def wikipedia_search(**kwargs) -> BaseTool:
    return WikipediaQueryRun(
        api_wrapper=WikipediaQueryInput()
    )
