from dataclasses import dataclass, field


@dataclass
class SonarCaseResult:
    case_id: str
    edit_mode: str
    applied: bool
    compiled: bool
    execution_time: float
    compile_time: float
    tests_ran: bool = False
    tests_passed: bool = False
    tests_run_count: int = 0
    tests_failed: int = 0
    tests_errored: int = 0
    tests_skipped: int = 0
    test_time: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    tokens_per_second: float = 0.0
    gpu_memory_mb: float | None = None
    gpu_power_w: float | None = None
    gpu_power_peak_w: float | None = None
    cpu_power_w: float | None = None
    cpu_power_peak_w: float | None = None
    energy_wh: float | None = None
    gpu_other_processes: int | None = None
    finish_reason: str | None = None
    system_fingerprint: str | None = None
    edit_match_summary: str | None = None
    error: str | None = None
    response_text: str | None = None
    tool_calls: list[dict] | None = None
    diff: str | None = None
    # Filled in by the SonarQube analysis phase. All defaulted so reports
    # written before that phase existed still load (validate_sonar_run.py and
    # analyze_sonar_run.py both rebuild this dataclass from report.json).
    sonar_analyzed: bool = False
    target_resolved: bool | None = None
    new_issues_count: int = 0
    new_issues: list[dict] = field(default_factory=list)
    remaining_target_issues: list[dict] = field(default_factory=list)
    baseline_issue_count: int = 0
    after_issue_count: int = 0
    sonar_time: float = 0.0
    sonar_error: str | None = None

    @property
    def clean_fix(self) -> bool:
        """The metric the suite actually cares about: the reported issue is
        gone, nothing new was introduced, and the behaviour tests still
        pass."""
        return bool(self.tests_passed and self.target_resolved and self.new_issues_count == 0)
