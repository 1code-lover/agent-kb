# PDF 手工测试检查清单

## 1. 目的
在正式手工测试 PDF 上传、切分、嵌入和问答之前，明确需要重点验证的链路和风险点。

当前代码显示：
- PDF 上传入口在 [frontend/KB_File.py](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/frontend/KB_File.py)
- 后端导入逻辑在 [api/services/kb_service.py](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/api/services/kb_service.py)
- 文件读取与索引写入在 [server/index.py](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/server/index.py)
- 切分与嵌入在 [server/text_splitter.py](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/server/text_splitter.py) 和 [server/ingestion.py](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/server/ingestion.py)
- 问答入口在 [frontend/Document_QA.py](C:/Users/ethan1.zhao/Downloads/agent-kb-main/github-agent-kb/frontend/Document_QA.py)

## 2. 当前高风险判断
从当前仓库依赖和代码来看，没有看到明确的 OCR 专用依赖或扫描 PDF 专门处理逻辑。

这意味着：
1. 文本型 PDF 可能可以正常解析。
2. 扫描版 PDF、图片型 PDF、复杂表格 PDF 很可能不是稳定支持项。
3. 这部分必须在手工测试中单独验证，不能默认“PDF 都能问答”。

## 3. 必测样本
手工测试时，至少准备下面 5 类 PDF：

1. 纯文本 PDF
说明：
- 正常段落
- 单栏排版
- 中文为主

2. 多页 PDF
说明：
- 至少 10 页
- 跨页连续内容
- 用于检查切分和页码来源

3. 表格较多的 PDF
说明：
- 看表格内容是否在问答中可被召回

4. 双栏或复杂排版 PDF
说明：
- 检查提取文本顺序是否错乱

5. 扫描版 PDF
说明：
- 检查是否完全无法提取文本
- 这是当前最高风险样本

## 4. 手工测试链路

### Step 1：上传阶段
检查项：
- 能否成功选择并上传 PDF
- 上传后文件名、类型、大小是否正常显示
- 特殊文件名是否被安全清理

重点风险：
- 大文件
- 中文文件名
- 重复文件名

### Step 2：切分阶段
检查项：
- `chunk_size` 和 `chunk_overlap` 可配置
- 保存后能触发索引构建
- 不同 PDF 类型下不会直接报错退出

重点风险：
- 文本被切得过碎，问答缺上下文
- 重叠过小导致答案断裂
- 重叠过大导致召回冗余

### Step 3：嵌入阶段
检查项：
- embedding 模型已就绪
- 索引生成成功
- 生成 chunk 数量合理，不是 0，也不是异常爆炸

重点风险：
- PDF 提取结果为空，但流程仍“成功”
- embedding 模型切换后已有索引表现不一致

### Step 4：问答阶段
检查项：
- 针对 PDF 中明确存在的信息提问，能否回答正确
- 是否能返回来源文件和页码
- 多轮提问是否稳定

重点风险：
- 回答正确率低但无明显报错
- 来源片段与答案不一致
- 页码缺失或错误

## 5. 关键验证问题
手工测试时建议直接问这些问题：

### 针对纯文本 PDF
- “文档的核心结论是什么？”
- “第二部分提到了哪些要点？”

### 针对多页 PDF
- “第 5 页提到的流程分几步？”
- “文档最后一页的结论是什么？”

### 针对表格 PDF
- “表格里某一列的取值范围是什么？”
- “某个具体数值出现在什么上下文里？”

### 针对扫描版 PDF
- “系统是否能返回有效答案？”
- “来源片段是否为空？”

## 6. 判定标准

### 可接受
- 纯文本 PDF 问答稳定
- 多页 PDF 可召回正确页内容
- 来源文件名和页码基本正确

### 不可接受
- 上传成功但实际没有有效 chunk
- 索引成功但问答长期答非所问
- 来源为空或和答案对不上
- 扫描版 PDF 被系统误判为“已正常导入”但实际无可用文本

## 7. 当前最重要结论
是的，PDF 问答识别、文本提取、切分和嵌入这条链路必须非常仔细地确保，尤其是：

1. PDF 是否真的提取到了有效文本
2. 切分后的 chunk 是否保留语义
3. 嵌入后检索是否能召回正确段落
4. 来源是否能反映真实页码和真实片段
5. 扫描版 PDF 是否需要明确标成“暂不支持”或后续补 OCR

## 8. 手工测试建议顺序
1. 先测纯文本 PDF
2. 再测多页 PDF
3. 再测表格和双栏 PDF
4. 最后单独测扫描版 PDF

## 9. 后续建议
如果扫描版 PDF 是必须场景，当前代码形态下应尽快补：
- OCR 能力评估
- 扫描 PDF 识别失败提示
- 导入后空文本检测
- 导入结果质量校验
