import pytest

from pkg.reponse import HttpCode


class TestBuiltinToolHandler:
    """内置工具处理器测试类"""

    def test_get_categories(self, client):
        """测试获取所有分类"""
        resp = client.get("/builtin-tools/categories")
        assert resp.status_code == 200
        assert resp.json.get("code") == HttpCode.SUCCESS
        assert len(resp.json.get("data")) > 0

    def test_get_buitin_tools(self, client):
        """测试获取所有内置工具"""
        resp = client.get("/builtin-tools")
        assert resp.status_code == 200
        assert resp.json.get("code") == HttpCode.SUCCESS
        assert len(resp.json.get("data")) > 0

    @pytest.mark.parametrize("provider_name, tool_name",
                             [
                                 ("google", "google_serper"),
                                 ("sam", "sam_search")
                             ])
    def test_get_provider_tool(self, provider_name, tool_name, client):
        resp = client.get(f"/builtin-tools/{provider_name}/tools/{tool_name}")
        assert resp.status_code == 200
        if provider_name == "google":
            assert resp.json.get("code") == HttpCode.SUCCESS
            assert resp.json.get("data").get("name") == tool_name
        elif provider_name == "sam":
            assert resp.json.get("code") == HttpCode.NOT_FOUNT

    @pytest.mark.parametrize(
        "provider_name",
        [
            "time",
            "sam"
        ]
    )
    def test_get_provider_icon(self, provider_name, client):
        """测试根据提供商获取Icon信息的接口"""
        resp = client.get(f"/builtin-tools/{provider_name}/icon")
        assert resp.status_code == 200
        if provider_name == "sam":
            assert resp.json.get("code") == HttpCode.NOT_FOUNT
