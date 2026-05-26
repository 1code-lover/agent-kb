"""
模块功能：
- 提供上传文件保存与文件名安全处理工具。

执行逻辑：
1. 根据配置返回上传保存目录。
2. 对文件名做路径穿越防护清洗。
3. 将上传内容写入目标目录并进行路径边界校验。
"""

import os
from config import DATA_DIR


def get_save_dir():
    """
    获取上传文件保存目录。

    Returns:
        str: 当前工作目录下的数据目录路径。
    """
    save_dir = os.getcwd() + "/" + DATA_DIR
    return save_dir


def sanitize_filename(filename: str) -> str:
    """
    清洗上传文件名，防止路径穿越攻击。

    Args:
        filename: 原始文件名。

    Returns:
        str: 安全可用的文件名。
    """
    # 先提取 basename，移除目录层级信息。
    filename = os.path.basename(filename)
    # 再次移除残留的路径标记，避免跨目录写入。
    filename = filename.replace("..", "").replace("/", "").replace("\\", "")
    # 清洗后为空或为隐藏文件名时回退为默认名，保证可落盘。
    if not filename or filename.startswith("."):
        filename = "uploaded_file"
    return filename


def save_uploaded_file(uploaded_file: bytes, save_dir: str):
    """
    保存上传文件到指定目录。

    输入：
    - uploaded_file: 上传文件对象（需包含 name/getbuffer 接口）。
    - save_dir(str): 目标保存目录。

    执行逻辑：
    1. 若目录不存在则先创建。
    2. 清洗文件名并拼接目标路径。
    3. 校验目标路径必须位于 save_dir 内部。
    4. 写入磁盘并输出保存日志。

    输出：
    - 无返回值；保存失败时记录错误日志。
    """
    try:
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        # 上传文件名必须先清洗，避免目录穿越。
        safe_filename = sanitize_filename(uploaded_file.name)
        path = os.path.join(save_dir, safe_filename)

        # 二次校验绝对路径边界，避免构造路径绕过。
        if not os.path.abspath(path).startswith(os.path.abspath(save_dir)):
            raise ValueError("Invalid file path detected")

        with open(path, "wb") as f:
            f.write(uploaded_file.getbuffer())
            print(f"已保存 {path}")
    except Exception as e:
        print(f"Error saving upload to disk: {e}")