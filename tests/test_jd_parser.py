import pytest
from unittest.mock import patch, MagicMock
from src.interview_eval.jd_parser import parse_jd, normalize_weights

def test_normalize_weights_basic():
    competencies = [
        {"id": "a", "weight": 10},
        {"id": "b", "weight": 30},
        {"id": "c", "weight": 60},
    ]
    result = normalize_weights(competencies)
    assert result[0]["weight"] == 0.1
    assert result[1]["weight"] == 0.3
    assert result[2]["weight"] == 0.6
    assert sum(c["weight"] for c in result) == pytest.approx(1.0)

def test_normalize_weights_zeros():
    competencies = [
        {"id": "a", "weight": 0},
        {"id": "b", "weight": 0},
    ]
    result = normalize_weights(competencies)
    assert result[0]["weight"] == 0.5
    assert result[1]["weight"] == 0.5

def test_normalize_weights_empty():
    assert normalize_weights([]) == []

@patch('src.interview_eval.jd_parser.chat_json')
@patch('src.interview_eval.jd_parser.get_client')
def test_parse_jd_success(mock_get_client, mock_chat_json):
    # Setup mocks
    mock_get_client.return_value = MagicMock()
    mock_chat_json.return_value = {
        "role_title": "Software Engineer",
        "competencies": [
            {
                "id": "python-skills",
                "name": "Python Mastery",
                "weight": 5,
                "description": "Strong Python knowledge",
                "signals": ["knows decorators", "understands async"]
            },
            {
                "id": "system-design",
                "name": "System Design",
                "weight": 5,
                "description": "Can design scalable systems",
                "signals": ["discusses load balancing"]
            }
        ]
    }

    result = parse_jd("some jd text")

    assert result["role_title"] == "Software Engineer"
    assert len(result["competencies"]) == 2
    assert result["competencies"][0]["id"] == "python-skills"
    assert result["competencies"][0]["weight"] == 0.5
    assert result["competencies"][1]["weight"] == 0.5

@patch('src.interview_eval.jd_parser.chat_json')
@patch('src.interview_eval.jd_parser.get_client')
def test_parse_jd_messy_data(mock_get_client, mock_chat_json):
    mock_get_client.return_value = MagicMock()
    mock_chat_json.return_value = {
        "role_title": "DevOps",
        "competencies": [
            # Valid
            {"id": "k8s", "name": "K8s", "weight": 10, "description": "desc", "signals": ["sig"]},
            # Missing ID, should slugify from name
            {"name": "Terraform", "weight": 10, "description": "desc", "signals": ["sig"]},
            # Missing name and ID, should be skipped
            {"weight": 10},
            # Duplicated ID (should be slugified with -x)
            {"id": "k8s", "name": "K8s Duplicate", "weight": 10, "description": "desc", "signals": ["sig"]},
            # Invalid type for weight
            {"id": "bash", "name": "Bash", "weight": "high", "description": "desc", "signals": ["sig"]},
        ]
    }

    result = parse_jd("some jd text")

    # Valid: k8s
    # Slugified: terraform
    # Skipped: {}
    # Duplicated: k8s-x
    # Invalid weight: bash (should default to 1.0)

    assert len(result["competencies"]) == 4
    ids = [c["id"] for c in result["competencies"]]
    assert "k8s" in ids
    assert "terraform" in ids
    assert "k8s-x" in ids
    assert "bash" in ids
