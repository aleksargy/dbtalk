from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from dbtalk.cli import cli

FIXTURE = Path(__file__).parent.parent / "fixtures" / "manifest.json"


def _make_mock_anthropic(tool_name: str = "get_lineage", tool_input: dict | None = None, answer: str = "fct_revenue depends on int_orders and stg_customers."):
    """Build a mock Anthropic client that returns a tool_use block then a text answer."""
    if tool_input is None:
        tool_input = {"model_name": "fct_revenue", "direction": "upstream", "depth": 0}

    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = tool_name
    tool_block.id = "tool_mock_id_001"
    tool_block.input = tool_input

    first_response = MagicMock()
    first_response.content = [tool_block]

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = answer
    # Ensure hasattr check works
    del text_block.tool_use_id

    second_response = MagicMock()
    second_response.content = [text_block]

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [first_response, second_response]
    return mock_client


def test_ask_exits_0_with_mock_api(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
    runner = CliRunner()
    with patch("dbtalk.agent.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value = _make_mock_anthropic()
        result = runner.invoke(cli, ["ask", "what does fct_revenue depend on?", "--manifest", str(FIXTURE)])
    assert result.exit_code == 0


def test_ask_output_contains_model_name(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
    runner = CliRunner()
    with patch("dbtalk.agent.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value = _make_mock_anthropic(answer="fct_revenue depends on int_orders and stg_customers.")
        result = runner.invoke(cli, ["ask", "what does fct_revenue depend on?", "--manifest", str(FIXTURE)])
    assert "fct_revenue" in result.output or "int_orders" in result.output


def test_missing_api_key_exits_1(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    runner = CliRunner()
    result = runner.invoke(cli, ["ask", "some question", "--manifest", str(FIXTURE)])
    assert result.exit_code == 1


def test_nonexistent_manifest_exits_1(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
    runner = CliRunner()
    result = runner.invoke(cli, ["ask", "some question", "--manifest", "/nonexistent/manifest.json"])
    assert result.exit_code == 1


def test_blast_radius_tool_dispatch(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
    runner = CliRunner()
    expected_answer = "Changing stg_orders affects int_orders, fct_revenue, and fct_customers."
    mock_client = _make_mock_anthropic(
        tool_name="blast_radius",
        tool_input={"model_name": "stg_orders"},
        answer=expected_answer,
    )
    with patch("dbtalk.agent.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value = mock_client
        result = runner.invoke(cli, ["ask", "what breaks if I change stg_orders?", "--manifest", str(FIXTURE)])
    assert result.exit_code == 0
    assert "stg_orders" in result.output or "int_orders" in result.output


def test_search_models_tool_dispatch(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
    runner = CliRunner()
    mock_client = _make_mock_anthropic(
        tool_name="search_models",
        tool_input={"query": "models with no tests"},
        answer="The following models have no tests: stg_orders, fct_customers.",
    )
    with patch("dbtalk.agent.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value = mock_client
        result = runner.invoke(cli, ["ask", "find models with no tests", "--manifest", str(FIXTURE)])
    assert result.exit_code == 0
