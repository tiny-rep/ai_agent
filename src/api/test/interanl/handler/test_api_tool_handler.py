import pytest

from internal.model import ApiToolProvider
from pkg.reponse import HttpCode

openapi_schema_string = """{"server": "https://baidu.com", "description": "123", "paths": 
{"/location": {"get": {"description": "获取本地位置", "operationId":"xxx", 
"parameters":[{"name":"location", "in":"query", "description":"参数描述", "required":true, "type":"str"}]}}}}"""


class TestApiToolHandler:

    @pytest.mark.parametrize("openapi_schema", [openapi_schema_string, "sam"])
    def test_validate_openapi_schema(self, openapi_schema, client):
        resp = client.post("/api-tools/validate-openapi-schema",
                           json={"openapi_schema": openapi_schema})
        assert resp.status_code == 200
        if openapi_schema == openapi_schema_string:
            print(resp.data)
            assert resp.json.get("code") == HttpCode.SUCCESS
        else:
            assert resp.json.get("code") == HttpCode.VALIDATE_ERROR

    @pytest.mark.parametrize("provider_id", [
        "fa4ab9ac-c832-4441-998d-581b39a28ab6",
        "fa4ab9ac-c832-4441-998d-581b39a28aef"
    ])
    def test_get_api_tool_provider(self, provider_id, client):
        resp = client.get(f"/api-tools/{provider_id}")
        assert resp.status_code == 200
        if provider_id.endswith("f"):
            assert resp.json.get("code") == HttpCode.FAIL
        else:
            assert resp.json.get("code") == HttpCode.SUCCESS

    @pytest.mark.parametrize("query", [
        {},
        {"current_page": 2},
        {"search_word": "测试"},
        {"search_word": "慕课"}
    ])
    def test_get_api_tool_providers_with_page(self, query, client):
        resp = client.get("/api-tools", query_string=query)
        assert resp.status_code == 200

        if query.get("current_page") == 2:
            assert len(resp.json.get("data").get("list")) == 0
        elif query.get("search_word") == "测试":
            assert len(resp.json.get("data").get("list")) == 0
        elif query.get("search_word") == "工具包":
            assert len(resp.json.get("data").get("list")) == 1
        else:
            assert resp.json.get("code") == HttpCode.SUCCESS

    @pytest.mark.parametrize("provider_id, tool_name", [
        {"fa4ab9ac-c832-4441-998d-581b39a28ab6", "GetCurrentWeather"},
        {"fa4ab9ac-c832-4441-998d-581b39a28ab6", "sam"}
    ])
    def test_get_api_tool(self, provider_id, tool_name, client):
        resp = client.get(f"/api-tools/{provider_id}/tools/{tool_name}")
        assert resp.status_code == 200

        if tool_name == "sam":
            assert resp.json.get("code") == HttpCode.NOT_FOUNT
        else:
            assert resp.json.get("code") == HttpCode.SUCCESS

    def test_create_api_tool_provider(self, client, db):
        data = {
            "name": "慕课学习工具包",
            "icon": "https://cdn.imooc.com/icon.png",
            "openapi_schema": "{\"description\":\"查询ip所在地、天气预报、路线规划等高德工具包\",\"server\":\"https://gaode.example.com\",\"paths\":{\"/weather\":{\"get\":{\"description\":\"根据传递的城市名获取指定城市的天气预报，例如：广州\",\"operationId\":\"GetCurrentWeather\",\"parameters\":[{\"name\":\"location\",\"in\":\"query\",\"description\":\"需要查询天气预报的城市名\",\"required\":true,\"type\":\"str\"}]}},\"/ip\":{\"post\":{\"description\":\"根据传递的ip查询ip归属地\",\"operationId\":\"GetCurrentIp\",\"parameters\":[{\"name\":\"ip\",\"in\":\"request_body\",\"description\":\"需要查询所在地的标准ip地址，例如:201.52.14.23\",\"required\":true,\"type\":\"str\"}]}}}}",
            "headers": [{"key": "Authorization", "value": "Bearer access_token"}]
        }
        resp = client.post("/api-tools", json=data)
        assert resp.status_code == 200
        assert resp.json.get("code") == HttpCode.SUCCESS

        from internal.model import ApiToolProvider
        api_tool_provider = db.session.query(ApiToolProvider).filter_by(name="慕课学习工具包").one_or_none()
        assert api_tool_provider is not None

    def test_update_api_tool_provider(self, client, db):
        provider_id = "fa4ab9ac-c832-4441-998d-581b39a28ab6"
        data = {
            "name": "慕课学习-test",
            "icon": "https://cdn.imooc.com/icon.png",
            "openapi_schema": "{\"description\":\"查询ip所在地、天气预报、路线规划等高德工具包\",\"server\":\"https://gaode.example.com\",\"paths\":{\"/weather\":{\"get\":{\"description\":\"根据传递的城市名获取指定城市的天气预报，例如：广州\",\"operationId\":\"GetCurrentWeather\",\"parameters\":[{\"name\":\"location\",\"in\":\"query\",\"description\":\"需要查询天气预报的城市名\",\"required\":true,\"type\":\"str\"}]}},\"/ip\":{\"post\":{\"description\":\"根据传递的ip查询ip归属地\",\"operationId\":\"GetCurrentIp\",\"parameters\":[{\"name\":\"ip\",\"in\":\"request_body\",\"description\":\"需要查询所在地的标准ip地址，例如:201.52.14.23\",\"required\":true,\"type\":\"str\"}]}}}}",
            "headers": [{"key": "Authorization", "value": "Bearer access_token"}]
        }
        resp = client.post(f"/api-tools/{provider_id}", json=data)
        assert resp.status_code == 200
        assert resp.json.get("code") == HttpCode.SUCCESS
        api_tool_provider = db.session.query(ApiToolProvider).get(provider_id)
        assert api_tool_provider is not None
        assert api_tool_provider.name == data.get("name")

    def test_delete_api_tool_provider(self, client, db):
        provider_id = "fa4ab9ac-c832-4441-998d-581b39a28ab6"
        resp = client.post(f"/api-tools/{provider_id}/delete")
        assert resp.status_code == 200
        assert resp.json.get("code") == HttpCode.SUCCESS

        from internal.model import ApiToolProvider
        api_tool_provider = db.session.query(ApiToolProvider).get(provider_id)
        assert api_tool_provider is None

    def test_create_api_tool_provider_mock(self, client):
        for i in range(100, 120):
            data = {
                "name": f"平台系统管理 {i}",
                "icon": "https://cdn.imooc.com/icon.png",
                "openapi_schema": "{\"description\":\"平台系统管理\",\"server\":\"http://sm-yt.mine-meta.cn/portal/api\",\"paths\":{\"/sub-sys/all\":{\"get\":{\"description\":\"获取子系统列表\",\"operationId\":\"sub-sys-all\",\"parameters\":[{\"name\":\"sysType\",\"in\":\"query\",\"description\":\"类型\",\"required\":true,\"type\":\"int\"}]}}}}",
                "headers": []
            }
            resp = client.post("/api-tools", json=data)
            assert resp.status_code == 200
