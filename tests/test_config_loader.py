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
