import json
import os

import pytest

import jsonio


def test_write_json_creates_parents_sorts_keys_and_ends_with_a_newline(tmp_path):
    target = tmp_path / "a" / "b" / "out.json"
    jsonio.write_json(str(target), {"b": 1, "a": "é"})
    text = target.read_text(encoding="utf-8")
    assert text == '{\n  "a": "é",\n  "b": 1\n}\n'
    assert os.listdir(target.parent) == ["out.json"]


def test_write_json_replaces_an_existing_file_without_leaving_a_temp(tmp_path):
    target = tmp_path / "out.json"
    target.write_text("{}")
    jsonio.write_json(target, {"k": 2})
    assert json.loads(target.read_text()) == {"k": 2}
    assert os.listdir(tmp_path) == ["out.json"]


def test_write_json_leaves_the_old_file_and_no_temp_when_the_value_cannot_encode(tmp_path):
    target = tmp_path / "out.json"
    target.write_text('{"keep": true}')
    with pytest.raises(TypeError):
        jsonio.write_json(target, {"bad": object()})
    assert json.loads(target.read_text()) == {"keep": True}
    assert os.listdir(tmp_path) == ["out.json"]


@pytest.mark.parametrize("content, message", [
    (None, "could not read context"),
    ("{not json", "could not read context"),
    ("[1]", "context must be a JSON object"),
])
def test_load_object_names_the_label_on_every_failure(tmp_path, content, message):
    path = tmp_path / "in.json"
    if content is not None:
        path.write_text(content)
    with pytest.raises(ValueError, match=message):
        jsonio.load_object(str(path), "context")


def test_load_object_returns_the_object(tmp_path):
    path = tmp_path / "in.json"
    path.write_text('{"a": 1}')
    assert jsonio.load_object(str(path)) == {"a": 1}
