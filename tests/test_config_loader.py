from runner.filesystem.config_loader import ConfigLoader
from runner.models.model_config import ModelConfig


def _make_config(**overrides) -> ModelConfig:
    defaults = dict(
        name="test-model",
        provider="llama.cpp",
        model="models/test.gguf",
        temperature=0.0,
        max_tokens=1024,
        context=4096,
        parameters={"n_gpu_layers": 16, "verbose": False},
    )
    defaults.update(overrides)
    return ModelConfig(**defaults)


def test_apply_device_cuda_is_a_no_op():
    config = _make_config()

    result = ConfigLoader.apply_device(config, "cuda")

    assert result is config
    assert result.parameters["n_gpu_layers"] == 16


def test_apply_device_cpu_forces_zero_gpu_layers():
    config = _make_config()

    result = ConfigLoader.apply_device(config, "cpu")

    assert result.parameters["n_gpu_layers"] == 0
    # other parameters are preserved
    assert result.parameters["verbose"] is False
    # original config is untouched
    assert config.parameters["n_gpu_layers"] == 16


def test_apply_device_cpu_works_even_without_existing_n_gpu_layers():
    config = _make_config(parameters={"verbose": True})

    result = ConfigLoader.apply_device(config, "cpu")

    assert result.parameters["n_gpu_layers"] == 0
    assert result.parameters["verbose"] is True


def test_apply_device_does_not_touch_non_llama_cpp_configs():
    config = _make_config(provider="openai", model="gpt-5", parameters={"timeout": 600})

    for device in ("cuda", "cpu"):
        result = ConfigLoader.apply_device(config, device)

        # n_gpu_layers is meaningless for a hosted model and would be
        # forwarded straight into the OpenAI client constructor.
        assert "n_gpu_layers" not in result.parameters
        assert result.parameters == {"timeout": 600}


def test_apply_device_rejects_unknown_device_for_every_provider():
    for provider in ("llama.cpp", "openai"):
        config = _make_config(provider=provider)

        try:
            ConfigLoader.apply_device(config, "tpu")
        except ValueError as error:
            assert "tpu" in str(error)
        else:
            raise AssertionError(f"no ValueError for provider={provider}")
