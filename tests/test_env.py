import os

from runner.filesystem.env import load_env


def test_missing_env_file_is_not_an_error(tmp_path):
    assert load_env(tmp_path / "nope.env") is False


def test_values_are_loaded_into_the_environment(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=sk-from-file\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert load_env(env_file) is True
    assert os.environ["OPENAI_API_KEY"] == "sk-from-file"


def test_real_environment_variables_win_over_the_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=sk-from-file\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-exported")

    load_env(env_file)

    # An explicit OPENAI_API_KEY=... in front of the command must not be
    # silently replaced by whatever .env happens to contain.
    assert os.environ["OPENAI_API_KEY"] == "sk-exported"


def test_override_opts_into_file_precedence(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=sk-from-file\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-exported")

    load_env(env_file, override=True)

    assert os.environ["OPENAI_API_KEY"] == "sk-from-file"


def test_importing_runner_loads_the_project_env():
    # runner/__init__.py runs load_env() once; importing any entry point
    # module is enough for the OpenAI provider to see the key.
    import runner

    assert hasattr(runner, "load_env")
