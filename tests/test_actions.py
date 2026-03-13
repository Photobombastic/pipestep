from pipestep.actions import get_action_equivalent


def test_checkout_has_equivalent():
    result = get_action_equivalent("actions/checkout@v4")
    assert result is not None
    desc, cmd = result
    assert "mounted" in desc.lower() or "checkout" in desc.lower() or "clone" in desc.lower()


def test_setup_node_has_equivalent():
    result = get_action_equivalent("actions/setup-node@v4")
    assert result is not None
    desc, cmd = result
    assert "node" in desc.lower()
    assert "nodejs" in cmd or "node" in cmd


def test_setup_python_has_equivalent():
    result = get_action_equivalent("actions/setup-python@v5")
    assert result is not None
    desc, cmd = result
    assert "python" in desc.lower()


def test_cache_has_equivalent():
    result = get_action_equivalent("actions/cache@v3")
    assert result is not None


def test_unknown_action_returns_none():
    result = get_action_equivalent("some-org/custom-action@v1")
    assert result is None


def test_version_agnostic():
    """All version tags should match for known actions."""
    for version in ["@v1", "@v2", "@v3", "@v4", "@main"]:
        result = get_action_equivalent(f"actions/checkout{version}")
        assert result is not None, f"Failed for actions/checkout{version}"


def test_setup_go_has_equivalent():
    result = get_action_equivalent("actions/setup-go@v5")
    assert result is not None


def test_setup_java_has_equivalent():
    result = get_action_equivalent("actions/setup-java@v4")
    assert result is not None


def test_upload_artifact_has_equivalent():
    result = get_action_equivalent("actions/upload-artifact@v4")
    assert result is not None


# --- with: input tests ---


def test_setup_node_with_version():
    desc, cmd = get_action_equivalent("actions/setup-node@v4", {"node-version": "18"})
    assert "18" in desc
    assert "setup_18" in cmd or "18" in cmd


def test_setup_python_with_version():
    desc, cmd = get_action_equivalent("actions/setup-python@v5", {"python-version": "3.11"})
    assert "3.11" in desc
    assert "3.11" in cmd


def test_setup_go_with_version():
    desc, cmd = get_action_equivalent("actions/setup-go@v5", {"go-version": "1.22"})
    assert "1.22" in desc
    assert "1.22" in cmd


def test_setup_java_with_version_and_distribution():
    desc, cmd = get_action_equivalent("actions/setup-java@v4", {"java-version": "17", "distribution": "corretto"})
    assert "17" in desc
    assert "corretto" in desc


def test_setup_node_without_version_is_generic():
    desc, cmd = get_action_equivalent("actions/setup-node@v4", {})
    assert "system default" in desc.lower() or "node" in desc.lower()


def test_with_inputs_ignored_for_noop_actions():
    desc, cmd = get_action_equivalent("actions/cache@v3", {"path": "node_modules", "key": "abc"})
    assert "no-op" in desc.lower()
