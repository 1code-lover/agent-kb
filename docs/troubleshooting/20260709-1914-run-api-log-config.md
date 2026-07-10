# 日志配置: `levelprefix` KeyError

## 现象

启动 `run_api.py` 时报错：

```
ValueError: Formatting field not found in record: 'levelprefix'
```

## 排查过程

1. 检查 `run_api.py` 中的 uvicorn `log_config` 自定义配置
2. 发现 `%(levelprefix)s` 是 uvicorn 自定义字段

## 根因

`%(levelprefix)s` 是 uvicorn 的 `DefaultFormatter` / `AccessFormatter` 自定义字段，标准 `logging.Formatter` 不认识。`RotatingFileHandler` 默认使用标准 Formatter，导致 `levelprefix` 未被解析。

## 修复

在 formatter 配置中添加 `"()"` 字段显式指定 uvicorn 的 formatter class：

```python
"default": {
    "()": "uvicorn.logging.DefaultFormatter",
    "format": "%(asctime)s  %(levelprefix)s  %(message)s",
    ...
}
"access": {
    "()": "uvicorn.logging.AccessFormatter",
    ...
}
```

## 效果 ✅
