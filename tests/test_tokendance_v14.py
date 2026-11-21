"""Offline TokenDance contract tests. Never send a real key or network request."""
import json

import httpx
import pytest

from enterprise.model_tools import ModelError, run_model_tools
from enterprise.provider_config import provider_configured, provider_name, resolve_provider


def synthetic_run():
    return {
        "plan": {
            "brand": "CONFIDENTIAL_BRAND_NOT_FOR_MODEL",
            "brief": "CONFIDENTIAL_BRIEF_NOT_FOR_MODEL",
            "industry": "食品饮料",
            "budget_wan": 200,
            "focus_landmark": "CONFIDENTIAL_LANDMARK",
            "candidate_count": 4,
            "item_count": 2,
            "selected": [{"line": "CONFIDENTIAL_MEDIA_DETAILS"}],
        },
        "quality_report": {"evidence": {"matched_items": 1}},
        "budget_variants": {
            "100": {"item_count": 1, "spent_wan": 85, "remaining_wan": 15},
            "200": {"item_count": 2, "spent_wan": 175, "remaining_wan": 25},
            "500": {"item_count": 3, "spent_wan": 400, "remaining_wan": 100},
        },
    }


def configure(monkeypatch):
    monkeypatch.setenv("COMPANYAGENT_MODEL_PROVIDER", "tokendance")
    monkeypatch.setenv("TOKENDANCE_MODEL", "glm-5.2")
    monkeypatch.setenv("TOKENDANCE_API_KEY", "fake-unit-test-key")


def test_provider_config_is_pinned_and_reports_readiness(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv("TOKENDANCE_BASE_URL", "https://attacker.invalid/steal")
    x = resolve_provider()
    assert x.name == "tokendance"
    assert x.endpoint == "https://tokendance.space/gateway/v1/chat/completions"
    assert x.model == "glm-5.2"
    assert x.api_key == "fake-unit-test-key"
    assert provider_name() == "tokendance"
    assert provider_configured()


def test_tokendance_multiple_real_protocol_tool_turns_are_mocked(monkeypatch):
    configure(monkeypatch)
    messages = iter([
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "call_a", "type": "function",
             "function": {"name": "inspect_inventory", "arguments": "{}"}}]},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "call_b", "type": "function",
             "function": {"name": "select_budget_scenario", "arguments": '{"budget_wan":100}'}}]},
        {"role": "assistant", "content": "参考 100 万情景，仍须人工核验库存。"},
    ])
    observed = []

    def handle(req):
        assert str(req.url) == "https://tokendance.space/gateway/v1/chat/completions"
        assert req.headers["authorization"] == "Bearer fake-unit-test-key"
        payload = json.loads(req.content)
        assert payload["model"] == "glm-5.2"
        assert payload["parallel_tool_calls"] is False
        assert payload["tool_choice"] == "auto"
        assert {t["function"]["name"] for t in payload["tools"]} == {
            "inspect_inventory", "select_budget_scenario"
        }
        serialized = json.dumps(payload, ensure_ascii=False)
        for secret in ("CONFIDENTIAL_BRAND", "CONFIDENTIAL_BRIEF", "CONFIDENTIAL_LANDMARK", "CONFIDENTIAL_MEDIA_DETAILS"):
            assert secret not in serialized
        observed.append(payload)
        return httpx.Response(200, json={"choices": [{"message": next(messages)}]})

    result = run_model_tools(
        synthetic_run(), {"inspect_inventory", "select_budget_scenario"},
        transport=httpx.MockTransport(handle)
    )
    assert len(observed) == 3
    assert [x["tool"] for x in result["executed_tools"]] == [
        "inspect_inventory", "select_budget_scenario"
    ]
    assert result["selected_scenario"]["budget_wan"] == 100
    assert result["selected_scenario"]["booked"] is False
    assert result["provider"] == "tokendance"
    assert result["model"] == "glm-5.2"
    assert result["mode"] == "mock_transport"
    assert result["verification_status"] == "tool_calls_executed"


def test_missing_token_and_model_fail_closed(monkeypatch):
    configure(monkeypatch)
    monkeypatch.delenv("TOKENDANCE_API_KEY")
    assert not provider_configured()
    with pytest.raises(ModelError, match="TOKENDANCE_API_KEY"):
        run_model_tools(synthetic_run(), {"inspect_inventory"})
    monkeypatch.setenv("TOKENDANCE_API_KEY", "dummy")
    monkeypatch.delenv("TOKENDANCE_MODEL")
    assert not provider_configured()
    with pytest.raises(ModelError, match="TOKENDANCE_MODEL"):
        run_model_tools(synthetic_run(), {"inspect_inventory"})


@pytest.mark.parametrize("bad_provider", ["https://attacker.invalid", "custom", "none"])
def test_unrecognized_provider_fails_closed(monkeypatch, bad_provider):
    monkeypatch.setenv("COMPANYAGENT_MODEL_PROVIDER", bad_provider)
    assert not provider_configured()
    with pytest.raises(ModelError, match="仅允许"):
        run_model_tools(synthetic_run(), {"inspect_inventory"}, api_key="fake")


def test_model_cannot_call_any_unauthorized_tool(monkeypatch):
    configure(monkeypatch)

    def handle(req):
        return httpx.Response(200, json={"choices": [{"message": {
            "role": "assistant",
            "tool_calls": [{"id": "c", "type": "function",
                            "function": {"name": "execute_shell", "arguments": "{}"}}]
        }}]})

    with pytest.raises(ModelError, match="未获授权"):
        run_model_tools(synthetic_run(), {"inspect_inventory"},
                        transport=httpx.MockTransport(handle))


def test_no_model_tool_called_does_not_count_as_tool_success(monkeypatch):
    configure(monkeypatch)
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json={"choices": [
            {"message": {"role": "assistant", "content": "建议人工核验"}}
        ]})
    )
    result = run_model_tools(synthetic_run(), {"inspect_inventory"}, transport=transport)
    assert result["executed_tools"] == []
    assert result["verification_status"] == "no_tool_calls"


def test_exhausted_model_turns_do_not_fake_completion(monkeypatch):
    configure(monkeypatch)
    def always_tool(req):
        return httpx.Response(200, json={"choices": [{"message": {
            "role": "assistant", "tool_calls": [
                {"id": "call", "type": "function",
                 "function": {"name": "inspect_inventory", "arguments": "{}"}}]
        }}]})
    with pytest.raises(ModelError, match="限定轮数"):
        run_model_tools(synthetic_run(), {"inspect_inventory"},
                        transport=httpx.MockTransport(always_tool), max_steps=2)


@pytest.mark.parametrize("status,expected", [
    (400, "HTTP 400"), (401, "HTTP 401"), (402, "HTTP 402"),
    (403, "HTTP 403"), (404, "HTTP 404"), (422, "HTTP 422"),
    (429, "HTTP 429"), (503, "HTTP 503"),
])
def test_live_gateway_errors_categorized_without_secret_or_body(monkeypatch, status, expected):
    configure(monkeypatch)
    sentinel = "TOP_SECRET_VALUE_SHOULD_NOT_BE_LOGGED"
    def reject(req):
        return httpx.Response(status, json={"error": {"message": sentinel}})
    with pytest.raises(ModelError) as exc:
        run_model_tools(synthetic_run(), {"inspect_inventory"},
                        transport=httpx.MockTransport(reject))
    assert expected in str(exc.value)
    assert sentinel not in str(exc.value)
    assert "fake-unit-test-key" not in str(exc.value)


def test_live_network_error_does_not_print_host_or_credentials(monkeypatch):
    configure(monkeypatch)
    def offline(req):
        raise httpx.ConnectError("TOP_SECRET_VALUE_SHOULD_NOT_BE_LOGGED")
    with pytest.raises(ModelError, match="网络连接失败") as exc:
        run_model_tools(synthetic_run(), {"inspect_inventory"},
                        transport=httpx.MockTransport(offline))
    assert "TOP_SECRET" not in str(exc.value)
