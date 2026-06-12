"""
文件功能：命令管道解析器测试
文件描述：验证 CommandParser 对管道、链接、转义引号等场景的解析能力
核心逻辑：通过断言检查解析结果的子命令列表和操作符列表是否符合预期
"""
from api.services.command_parser import CommandParser


def test_pipe_chain_is_split():
    """
    函数名：test_pipe_chain_is_split
    入参：无
    功能：验证管道命令被正确拆分为子命令
    运行逻辑：解析 "cat file.txt | grep error | wc -l"，断言子命令和操作符
    出参：无
    """
    parsed = CommandParser.parse("cat file.txt | grep error | wc -l")
    assert parsed.sub_commands == ["cat file.txt", "grep error", "wc -l"]
    assert parsed.operators == ["|", "|"]


def test_and_chain_is_split():
    """
    函数名：test_and_chain_is_split
    入参：无
    功能：验证 && 操作符命令被正确拆分
    运行逻辑：解析 "make && make install"，断言子命令和操作符
    出参：无
    """
    parsed = CommandParser.parse("make && make install")
    assert parsed.sub_commands == ["make", "make install"]
    assert parsed.operators == ["&&"]


def test_escaped_quotes():
    """
    函数名：test_escaped_quotes
    入参：无
    功能：验证转义引号内的内容不会被操作符拆分
    运行逻辑：解析包含转义引号的管道命令，断言子命令数量为2
    出参：无
    """
    parsed = CommandParser.parse('echo "hello \\"world\\"" | grep hello')
    assert len(parsed.sub_commands) == 2


def test_semicolon_chain():
    """
    函数名：test_semicolon_chain
    入参：无
    功能：验证分号操作符命令被正确拆分
    运行逻辑：解析 "echo hello; echo world"，断言子命令和操作符
    出参：无
    """
    parsed = CommandParser.parse("echo hello; echo world")
    assert parsed.sub_commands == ["echo hello", "echo world"]
    assert parsed.operators == [";"]


def test_mixed_operators():
    """
    函数名：test_mixed_operators
    入参：无
    功能：验证混合操作符命令被正确拆分
    运行逻辑：解析包含 | 和 && 的命令，断言子命令数量为3，操作符为 ["|", "&&"]
    出参：无
    """
    parsed = CommandParser.parse("cat file.txt | grep error && echo done")
    assert len(parsed.sub_commands) == 3
    assert parsed.operators == ["|", "&&"]
