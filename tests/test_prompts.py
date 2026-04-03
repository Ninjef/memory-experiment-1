"""Tests for the pluggable prompt system."""

import pytest

from src.prompts import load_prompt
from src.prompts.default import Prompt as DefaultPrompt
from src.prompts.insight_generating import Prompt as InsightGeneratingPrompt


class TestDefaultPrompt:
    def test_system_prompt_is_string(self):
        p = DefaultPrompt()
        assert isinstance(p.system_prompt(), str)
        assert len(p.system_prompt()) > 0

    def test_parse_response_array(self):
        p = DefaultPrompt()
        raw = [{"text": "insight one"}, {"text": "insight two"}]
        result = p.parse_response(raw)
        assert len(result) == 2
        assert result[0]["insight"] == "insight one"
        assert result[1]["insight"] == "insight two"

    def test_parse_response_single_object(self):
        p = DefaultPrompt()
        raw = {"text": "solo insight"}
        result = p.parse_response(raw)
        assert len(result) == 1
        assert result[0]["insight"] == "solo insight"


class TestInsightGeneratingPrompt:
    def test_system_prompt_is_string(self):
        p = InsightGeneratingPrompt()
        assert isinstance(p.system_prompt(), str)
        assert "psychiatry" in p.system_prompt().lower()

    def test_parse_response_single_object(self):
        p = InsightGeneratingPrompt()
        raw = {
            "insight": "User shows pattern of avoidance",
            "confidence": 8.0,
            "suggestedAction": "Explore underlying fears",
        }
        result = p.parse_response(raw)
        assert len(result) == 1
        assert result[0]["insight"] == "User shows pattern of avoidance"
        assert result[0]["confidence"] == 8.0
        assert result[0]["suggestedAction"] == "Explore underlying fears"

    def test_parse_response_array(self):
        p = InsightGeneratingPrompt()
        raw = [
            {"insight": "A", "confidence": 5, "suggestedAction": "Do A"},
            {"insight": "B", "confidence": 3},
        ]
        result = p.parse_response(raw)
        assert len(result) == 2
        assert result[0]["insight"] == "A"
        assert result[1]["suggestedAction"] is None


class TestPromptLoading:
    def test_load_default(self):
        p = load_prompt("default")
        assert hasattr(p, "system_prompt")
        assert hasattr(p, "parse_response")

    def test_load_insight_generating(self):
        p = load_prompt("insight_generating")
        assert hasattr(p, "system_prompt")
        assert hasattr(p, "parse_response")

    def test_load_invalid_raises(self):
        with pytest.raises(ModuleNotFoundError):
            load_prompt("nonexistent_prompt_module")
