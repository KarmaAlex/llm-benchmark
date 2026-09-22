from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_DIR = PROJECT_ROOT / "benchmark"
CONFIG_DIR = PROJECT_ROOT / "configs"
PROMPT_DIR = PROJECT_ROOT / "prompts"
RESULTS_DIR = PROJECT_ROOT / "results"

# Machine-local, gitignored scratch: caches that are expensive to rebuild but
# derivable from the repo (pristine sonar baselines) and the Maven repository
# shared by every scanner invocation so analyses don't re-download the world.
CACHE_DIR = PROJECT_ROOT / ".cache"
SONAR_BASELINE_CACHE_DIR = CACHE_DIR / "sonar-baselines"
MAVEN_REPO_DIR = CACHE_DIR / "maven-repo"
SONAR_SCRATCH_DIR = CACHE_DIR / "sonar-scratch"