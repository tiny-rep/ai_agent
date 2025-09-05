## 工作流测试代码

```python
from internal.core.workflow import Workflow
from internal.core.workflow.entities.workflow_entity import WorkflowConfig

nodes = [
    {
        "id": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
        "node_type": "start",
        "title": "开始",
        "description": "工作流的起点节点，支持定义工作流的起点输入等信息。",
        "inputs": [
            {
                "name": "query",
                "type": "string",
                "description": "用户输入的query信息",
                "required": True,
                "value": {
                    "type": "generated",
                    "content": "",
                }
            },
            {
                "name": "location",
                "type": "string",
                "description": "需要查询的城市地址信息",
                "required": False,
                "value": {
                    "type": "generated",
                    "content": "",
                }
            },
            {
                "name": "search",
                "type": "string",
                "description": "需要搜索知识库的内容",
                "required": False,
                "value": {
                    "type": "generated",
                    "content": "",
                }
            }
        ]
    },
    {
        "id": "860c8411-37ed-4872-b53f-30afa0290211",
        "node_type": "end",
        "title": "结束",
        "description": "工作流的结束节点，支持定义工作流最终输出的变量等信息。",
        "outputs": [
            {
                "name": "query",
                "type": "string",
                "value": {
                    "type": "ref",
                    "content": {
                        "ref_node_id": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
                        "ref_var_name": "query",
                    },
                }
            },
            {
                "name": "location",
                "type": "string",
                "value": {
                    "type": "ref",
                    "content": {
                        "ref_node_id": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
                        "ref_var_name": "location",
                    },
                }
            },
            {
                "name": "llm_output",
                "type": "string",
                "value": {
                    "type": "ref",
                    "content": {
                        "ref_node_id": "eba75e0b-21b7-46ed-8d21-791724f0740f",
                        "ref_var_name": "output",
                    },
                }
            },
            {
                "name": "gaode_content",
                "type": "string",
                "value": {
                    "type": "ref",
                    "content": {
                        "ref_node_id": "2f6cf40d-0219-421b-92ff-229fdde15ecb",
                        "ref_var_name": "text",
                    },
                }
            },
            {
                "name": "username",
                "type": "string",
                "value": {
                    "type": "literal",
                    "content": "sam",
                }
            }
        ]
    },
    {
        "id": "675fca50-1228-8008-82dc-0c714158534c",
        "node_type": "http_request",
        "title": "HTTP请求",
        "description": "",
        "url": "https://www.cnblogs.com/",
        "method": "get",
        "inputs": [],
    },
    {
        "id": "eba75e0b-21b7-46ed-8d21-791724f0740f",
        "node_type": "llm",
        "title": "大语言模型",
        "description": "",
        "inputs": [
            {
                "name": "query",
                "type": "string",
                "value": {
                    "type": "ref",
                    "content": {
                        "ref_node_id": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
                        "ref_var_name": "query",
                    },
                }
            },
            {
                "name": "context",
                "type": "string",
                "value": {
                    "type": "ref",
                    "content": {
                        "ref_node_id": "675fca50-1228-8008-82dc-0c714158534c",
                        "ref_var_name": "text",
                    },
                }
            },
            {
                "name": "documents",
                "type": "string",
                "value": {
                    "type": "ref",
                    "content": {
                        "ref_node_id": "868b5769-1925-4e7b-8aa4-af7c3d444d91",
                        "ref_var_name": "combine_documents",
                    },
                }
            }
        ],
        "prompt": (
            "你是一个强有力的AI机器人，请根据用户的提问回复特定的内容，用户的提问是: {{query}}。\n\n"
            "如果有必要，可以使用上下文内容进行回复，上下文内容:\n\n<context>{{context}}</context>\n\n<context>{{documents}}</context>"
        ),
        "model_config": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "parameters": {
                "temperature": 0.5,
                "top_p": 0.85,
                "frequency_penalty": 0.2,
                "presence_penalty": 0.2,
                "max_tokens": 8192,
            },
        }
    },
    {
        "id": "623b7671-0bc2-446c-bf5e-5e25032a522e",
        "node_type": "template_transform",
        "title": "模板转换",
        "description": "",
        "inputs": [
            {
                "name": "location",
                "type": "string",
                "value": {
                    "type": "ref",
                    "content": {
                        "ref_node_id": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
                        "ref_var_name": "location",
                    },
                }
            },
            {
                "name": "query",
                "type": "string",
                "value": {
                    "type": "ref",
                    "content": {
                        "ref_node_id": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
                        "ref_var_name": "query"
                    }
                }
            }
        ],
        "template": "地址: {{location}}\n提问内容: {{query}}",
    },
    {
        "id": "868b5769-1925-4e7b-8aa4-af7c3d444d91",
        "node_type": "dataset_retrieval",
        "title": "知识库检索",
        "description": "",
        "inputs": [
            {
                "name": "query",
                "type": "string",
                "value": {
                    "type": "ref",
                    "content": {
                        "ref_node_id": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
                        "ref_var_name": "search"
                    }
                }
            }
        ],
        "dataset_ids": [
            "98a495c1-b46d-40f1-a4e9-55a9274d16a6"
        ],
    },
    {
        "id": "4a9ed43d-e886-49f7-af9f-9e85d83b27aa",
        "node_type": "code",
        "title": "代码",
        "description": "",
        "inputs": [
            {
                "name": "combine_documents",
                "type": "string",
                "value": {
                    "type": "ref",
                    "content": {
                        "ref_node_id": "868b5769-1925-4e7b-8aa4-af7c3d444d91",
                        "ref_var_name": "combine_documents",
                    },
                }
            },
        ],
        "code": """def main(params):
            return {
                "first_100_documents": params.get("combine_documents", "")[:100]
            }""",
        "outputs": [
            {
                "name": "first_100_documents",
                "type": "string",
                "value": {
                    "type": "generated",
                    "content": "",
                }
            }
        ]
    },
    {
        "id": "2f6cf40d-0219-421b-92ff-229fdde15ecb",
        "node_type": "tool",
        "title": "内置工具",
        "description": "",
        "type": "builtin_tool",
        "provider_id": "gaode",
        "tool_id": "gaode_weather",
        "inputs": [
            {
                "name": "city",
                "type": "string",
                "value": {
                    "type": "ref",
                    "content": {
                        "ref_node_id": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
                        "ref_var_name": "location"
                    }
                }
            }
        ]
    }
]

edges = [
    # 并行线路1
    {
        "id": "675fca50-1228-8008-82dc-0c714158534c",
        "source": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
        "source_type": "start",
        "target": "868b5769-1925-4e7b-8aa4-af7c3d444d91",
        "target_type": "dataset_retrieval",
    },
    {
        "id": "675fcd37-f308-8008-a6f4-389a0b1ed0ea",
        "source": "868b5769-1925-4e7b-8aa4-af7c3d444d91",
        "source_type": "dataset_retrieval",
        "target": "eba75e0b-21b7-46ed-8d21-791724f0740f",
        "target_type": "llm",
    },
    {
        "id": "675fa28c-6f94-8008-b5ae-2eba3300b2e6",
        "source": "eba75e0b-21b7-46ed-8d21-791724f0740f",
        "source_type": "llm",
        "target": "4a9ed43d-e886-49f7-af9f-9e85d83b27aa",
        "target_type": "code",
    },
    {
        "id": "675f9964-0028-8008-8046-d017996f3d3c",
        "source": "4a9ed43d-e886-49f7-af9f-9e85d83b27aa",
        "source_type": "code",
        "target": "860c8411-37ed-4872-b53f-30afa0290211",
        "target_type": "end",
    },

    # 并行线路2
    {
        "id": "675f9290-5990-8008-ab62-5a0ff8d95edc",
        "source": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
        "source_type": "start",
        "target": "675fca50-1228-8008-82dc-0c714158534c",
        "target_type": "http_request",
    },
    {
        "id": "675f90b4-7bb8-8008-8b72-ba26ce50951c",
        "source": "675fca50-1228-8008-82dc-0c714158534c",
        "source_type": "http_request",
        "target": "eba75e0b-21b7-46ed-8d21-791724f0740f",
        "target_type": "llm",
    },
    {
        "id": "675fcd37-f308-8008-a6f4-389a0b1ed0ca",
        "source": "eba75e0b-21b7-46ed-8d21-791724f0740f",
        "source_type": "llm",
        "target": "623b7671-0bc2-446c-bf5e-5e25032a522e",
        "target_type": "template_transform",
    },
    {
        "id": "675f8c7e-e600-8008-885b-6a1271cb4365",
        "source": "623b7671-0bc2-446c-bf5e-5e25032a522e",
        "source_type": "template_transform",
        "target": "860c8411-37ed-4872-b53f-30afa0290211",
        "target_type": "end",
    },
    # 并行线路3
    {
        "id": "675f850a-de28-8008-9f27-d508d8337e49",
        "source": "18d938c4-ecd7-4a6b-9403-3625224b96cc",
        "source_type": "start",
        "target": "2f6cf40d-0219-421b-92ff-229fdde15ecb",
        "target_type": "tool",
    },
    {
        "id": "675f8403-cbf4-8008-9aae-76ecae12c675",
        "source": "2f6cf40d-0219-421b-92ff-229fdde15ecb",
        "source_type": "tool",
        "target": "860c8411-37ed-4872-b53f-30afa0290211",
        "target_type": "end",
    }
]

workflow_config = WorkflowConfig(
    account_id=current_user.id,
    name="workflow",
    description="工作流组件",
    nodes=nodes,
    edges=edges
)
workflow = Workflow(workflow_config=workflow_config)
result = workflow.invoke(
    {"query": "关于LLM的文章有哪些？以及电子围栏是什么？", "location": "重庆", "search": "电子围栏是什么？"})
result_dict = convert_model_to_dict(result)
return success_json({
    **result_dict,
    "info": {
        "name": workflow.name,
        "description": workflow.description
    }
})
```

## 带参数的OpenAPI

```json
{
  "server": "http://sm-yt.mine-meta.cn",
  "description": "综合管理平台相关接口，包含安全监控、精确定位等子系统",
  "paths": {
    "/portal/api/home/in-well-person": {
      "get": {
        "description": "获取当前井下人员列表",
        "operationId": "getInwellInfo",
        "parameters": []
      }
    },
    "/io/api/realdata/GetDevRt": {
      "get": {
        "description": "获取指定系统的设备基础和状态信息列表",
        "operationId": "getDeviceRealData",
        "parameters": [
          {
            "name": "sysId",
            "in": "query",
            "description": "系统编号，安全监控的系统编号为1001，精确定位的系统编号为1002",
            "required": true,
            "type": "str"
          }
        ]
      }
    }
  }
}
```