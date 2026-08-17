# 知识库物理隔离、Embedding 缓存恢复与 OCR 版面增强

## 基本信息
- 类型：feature
- 日期：2026-08-17
- 相关模块：多知识库存储、Embedding 运行时恢复、Knowledge Workspace、图片/PDF OCR、质量评测与产品文档
- 相关文件：`server/stores/storage_context.py`、`api/runtime.py`、`api/services/embedding_cache_service.py`、`api/routers/embedding_cache.py`、`server/readers/image_ocr.py`、`server/readers/pdf_ocr.py`、`scripts/pdf_ocr_quality.py`、`webapp/src/pages/KnowledgePage.jsx`、`webapp/src/components/kb/KbWorkspaceHeader.jsx`

## 需求背景
项目原来已经有多知识库的范围契约，但索引仍共享同一存储，隔离强度依赖 `kb_id` 过滤；同时桌面环境禁用运行时远程下载后，Embedding 缓存缺失只能由用户离开产品手工处理。OCR 虽然能提取文本，也缺少基于几何信息的阅读顺序、表格结构和页级诊断。本轮目标是在跳过 Apple 证书、签名和公证的前提下，先完成这些不依赖外部门禁的本地产品能力。

## 设计与实现方案
1. 存储层保留 `default -> storage/` 的历史兼容路径，非 default 知识库统一进入 `storage/kbs/{kb_id}/`。每个显式持久化目录创建或恢复独立 `StorageContext`，Folder 列表和查询范围均按目标 KB 获取对应的 `IndexManager`，对外回显更新为 `physical_isolated`。
2. 新增 Embedding 缓存恢复服务和 API，固定只接受 `modelscope` provider，状态机为 `idle/downloading/ready/failed`。下载成功后清除旧的 LlamaIndex embedding 运行时状态并重新触发后台预热；前端在缓存缺失诊断出现时展示恢复按钮、下载状态、失败原因和重试入口。
3. OCR 侧统一解析 `rec_texts`、`rec_boxes`、`dt_polys`、`rec_scores`，兼容 NumPy 数组；按 y 坐标聚类行、按 x 坐标恢复行内顺序，稳定矩形结构输出 Markdown table，不规则版面回退为 geometry lines。扫描 PDF 保留 `[Page N]` 标记并汇总行数、表格行列和平均置信度。
4. 质量脚本增加阅读顺序准确率与表格单元格召回；评测 fixture 和当前代码统一使用 `physical_isolated`。历史 artifacts 不重写，文档明确旧共享索引中的非 default 数据需要重新导入或重建。
5. 代码评审发现下载线程“已登记但尚未 start”的并发窗口，使用一个可控线程测试先稳定复现失败，再把判重、状态写入、线程登记和 `thread.start()` 收进同一服务锁边界。

## 为什么选这个方案
物理目录隔离可以直接复用现有 LlamaIndex `StorageContext` 和 `IndexManager` 结构，改动范围小，同时保留 default 知识库的历史数据兼容。Embedding 恢复复用已有缓存准备脚本，API 只开放固定 ModelScope 白名单，比允许任意 URL 或 shell 命令更安全，也能形成桌面端可观察、可重试的产品闭环。OCR 先利用 PaddleOCR 已返回的几何信息做确定性重排，不引入新的大型版面模型，能在当前依赖锁和本地运行约束下快速提升表格与阅读顺序质量。

## 其他方案与为什么没选
1. 自动拆分历史共享索引：旧节点、文档和向量的归属与完整性需要专门迁移设计，静默搬运风险较高，因此本轮选择明确提示重新导入或重建。
2. 允许前端提交任意下载源或模型 URL：会扩大 SSRF、供应链和配置复杂度，本轮只开放固定 ModelScope 映射。
3. 直接引入专用版面分析/表格识别模型：会增加模型体积、缓存准备、冷启动和打包依赖，本轮先使用现有 OCR geometry 的确定性启发式。
4. 为了继续开发而绕过 Apple 发布门禁：签名、公证属于正式分发要求，不能伪造完成状态；本轮只验收本地功能和构建测试。

## 风险与权衡
非 default 知识库升级后不会自动继承旧共享索引数据，需要用户重建。目录级物理隔离提升了跨库边界，但不等价于企业级多租户权限、加密隔离或远程安全认证，因此 default-deny 和 `kb_id` 范围回显仍保留为纵深防御。Embedding 下载依赖 ModelScope 网络与本地磁盘，失败状态会被保留供重试。表格识别是规则启发式，只在多行等列的稳定二维结构上输出 Markdown table，混合标题或不规则表格会诚实回退为普通阅读顺序文本。

## 验证与结果
- TDD 并发测试初次执行：`1 failed, 3 passed`，证明 pre-start 重复线程窗口真实存在；修复后 `4 passed`。
- Python 非 slow 全量：`803 passed, 1 deselected, 36 warnings`。
- Web 全量 Node tests：`90 passed`。
- Vite production build：通过。
- Electron 全量测试：`86 passed`。
- 修改模块覆盖率切片：`55 passed`，`TOTAL 85%`。
- `git diff --check`：通过。
- 当前代码、测试和 `eval_v1` 到 `eval_v6` fixture 中无 `logical_filter_only` 残留；fixture 语义审计确认改动仅为 `logical_filter_only -> physical_isolated`。
- 证书、Developer ID 签名、公证与 stapling 未执行，因此没有宣称正式 macOS 发布完成。

## 面试表达版本
我把原来依赖 metadata 过滤的多知识库升级成了目录级物理索引隔离，同时保留 default 知识库的历史路径。针对桌面环境禁用远程下载后的 Embedding 缓存缺失，我增加了固定 ModelScope 白名单的后台恢复 API 和前端可重试状态机。OCR 侧利用现有几何框恢复阅读顺序和规则表格，不额外引入重型版面模型。评审时我还用并发测试复现并修掉了线程登记到启动之间的重复下载窗口。最终 Python 803 个、Web 90 个、Electron 86 个测试全部通过，修改模块覆盖率 85%，而 Apple 签名公证仍按真实状态保留为正式发布阻断项。
