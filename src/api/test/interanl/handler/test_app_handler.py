import pytest

from pkg.reponse import HttpCode


class TestAppHandler:
    @pytest.mark.parametrize("query", [None, "您好，您是谁"])
    def test_completion(self, query, client):
        resp = client.post('/app/completion', json={"query": query})
        assert resp.status_code == 200
        if query is None:
            assert resp.json.get("code") == HttpCode.VALIDATE_ERROR
        else:
            assert resp.json.get("code") == HttpCode.SUCCESS
        print("响应：", resp.json)
