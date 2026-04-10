"""Tests for scripts/compare_runs.py."""

from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

import pytest

# Import from scripts — add scripts dir to path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from compare_runs import text_hash, load_coords, match_points, load_config, build_payload


def _write_csv(path: Path, rows: list[dict]) -> None:
    """Helper to write a viz_coords CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["id", "cluster_id", "x", "y", "z", "text"]
        )
        writer.writeheader()
        writer.writerows(rows)


class TestTextHash:
    def test_consistency(self):
        assert text_hash("hello") == text_hash("hello")

    def test_different_texts(self):
        assert text_hash("hello") != text_hash("world")

    def test_length(self):
        assert len(text_hash("anything")) == 16

    def test_hex_chars(self):
        h = text_hash("test")
        assert all(c in "0123456789abcdef" for c in h)


class TestLoadCoords:
    def test_loads_csv(self, tmp_path):
        run_dir = tmp_path / "run_1"
        _write_csv(run_dir / "viz_coords.csv", [
            {"id": "a", "cluster_id": "0", "x": "1.0", "y": "2.0", "z": "3.0", "text": "hello"},
            {"id": "b", "cluster_id": "1", "x": "4.0", "y": "5.0", "z": "6.0", "text": "world"},
        ])
        rows = load_coords(run_dir, "viz_coords.csv")
        assert len(rows) == 2
        assert rows[0]["x"] == 1.0
        assert rows[1]["cluster_id"] == 1
        assert rows[0]["text"] == "hello"

    def test_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_coords(tmp_path, "viz_coords.csv")


class TestMatchPoints:
    def test_full_overlap(self):
        run_a = [
            {"id": "1", "cluster_id": 0, "x": 1.0, "y": 2.0, "z": 3.0, "text": "hello"},
            {"id": "2", "cluster_id": 1, "x": 4.0, "y": 5.0, "z": 6.0, "text": "world"},
        ]
        run_b = [
            {"id": "3", "cluster_id": 2, "x": 7.0, "y": 8.0, "z": 9.0, "text": "hello"},
            {"id": "4", "cluster_id": 3, "x": 10.0, "y": 11.0, "z": 12.0, "text": "world"},
        ]
        points = match_points([run_a, run_b])
        assert len(points) == 2
        for p in points:
            assert p["positions"][0] is not None
            assert p["positions"][1] is not None

    def test_partial_overlap(self):
        run_a = [
            {"id": "1", "cluster_id": 0, "x": 1.0, "y": 2.0, "z": 3.0, "text": "hello"},
        ]
        run_b = [
            {"id": "2", "cluster_id": 1, "x": 4.0, "y": 5.0, "z": 6.0, "text": "world"},
        ]
        points = match_points([run_a, run_b])
        assert len(points) == 2

        hello_point = next(p for p in points if p["text"].startswith("hello"))
        world_point = next(p for p in points if p["text"].startswith("world"))

        assert hello_point["positions"][0] is not None
        assert hello_point["positions"][1] is None
        assert world_point["positions"][0] is None
        assert world_point["positions"][1] is not None

    def test_collision_keeps_first(self):
        # Two entries with identical text in the same run — should keep first
        run_a = [
            {"id": "1", "cluster_id": 0, "x": 1.0, "y": 2.0, "z": 3.0, "text": "same"},
            {"id": "2", "cluster_id": 1, "x": 99.0, "y": 99.0, "z": 99.0, "text": "same"},
        ]
        points = match_points([run_a])
        assert len(points) == 1
        assert points[0]["positions"][0]["x"] == 1.0  # kept first

    def test_text_truncated_to_200(self):
        long_text = "a" * 500
        run_a = [
            {"id": "1", "cluster_id": 0, "x": 1.0, "y": 2.0, "z": 3.0, "text": long_text},
        ]
        points = match_points([run_a])
        assert len(points[0]["text"]) == 200


class TestLoadConfig:
    def test_valid_basic(self, tmp_path):
        config = {
            "runs": [
                {"path": "run_a", "label": "A"},
                {"path": "run_b", "label": "B"},
            ]
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config))
        result = load_config(config_path)
        assert len(result["runs"]) == 2

    def test_too_few_runs(self, tmp_path):
        config = {"runs": [{"path": "run_a"}]}
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config))
        with pytest.raises(ValueError, match="at least 2"):
            load_config(config_path)

    def test_missing_path(self, tmp_path):
        config = {"runs": [{"label": "A"}, {"label": "B"}]}
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config))
        with pytest.raises(ValueError, match="path"):
            load_config(config_path)

    def test_valid_side_by_side(self, tmp_path):
        config = {
            "sideBySide": {
                "left": {
                    "title": "Left",
                    "runs": [
                        {"path": "a", "label": "A"},
                        {"path": "b", "label": "B"},
                    ]
                },
                "right": {
                    "title": "Right",
                    "runs": [
                        {"path": "c", "label": "C"},
                        {"path": "d", "label": "D"},
                    ]
                }
            }
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config))
        result = load_config(config_path)
        assert "sideBySide" in result

    def test_side_by_side_too_few_runs(self, tmp_path):
        config = {
            "sideBySide": {
                "left": {"runs": [{"path": "a"}]},
                "right": {"runs": [{"path": "b"}, {"path": "c"}]},
            }
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config))
        with pytest.raises(ValueError, match="at least 2"):
            load_config(config_path)


class TestBuildPayload:
    def test_single_mode(self, tmp_path):
        for name in ("run_a", "run_b"):
            _write_csv(tmp_path / name / "viz_coords.csv", [
                {"id": "1", "cluster_id": "0", "x": "1.0", "y": "2.0", "z": "3.0", "text": "hello"},
            ])
        config = {
            "coordsFile": "viz_coords.csv",
            "runs": [
                {"path": str(tmp_path / "run_a"), "label": "A"},
                {"path": str(tmp_path / "run_b"), "label": "B"},
            ],
        }
        payload = build_payload(config)
        assert payload["mode"] == "single"
        assert len(payload["runs"]) == 2
        assert len(payload["points"]) == 1

    def test_side_by_side_mode(self, tmp_path):
        for name in ("run_a", "run_b"):
            _write_csv(tmp_path / name / "coords.csv", [
                {"id": "1", "cluster_id": "0", "x": "1.0", "y": "2.0", "z": "3.0", "text": "hello"},
            ])
        config = {
            "coordsFile": "coords.csv",
            "sideBySide": {
                "left": {
                    "title": "Left",
                    "runs": [
                        {"path": str(tmp_path / "run_a"), "label": "A"},
                        {"path": str(tmp_path / "run_b"), "label": "B"},
                    ],
                },
                "right": {
                    "title": "Right",
                    "runs": [
                        {"path": str(tmp_path / "run_a"), "label": "C"},
                        {"path": str(tmp_path / "run_b"), "label": "D"},
                    ],
                },
            },
        }
        payload = build_payload(config)
        assert payload["mode"] == "sideBySide"
        assert payload["left"]["title"] == "Left"
        assert len(payload["left"]["points"]) == 1
