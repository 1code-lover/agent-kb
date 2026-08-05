# Single KB Scope Contract

Single-kb chat responses must echo the following fields exactly:
- requested_scope_type
- requested_kb_ids
- effective_scope_type
- effective_kb_ids
- is_default_deny_applied
- isolation_level

The effective scope must stay inside the explicitly requested knowledge base.
中文补充：回答必须回显 requested_scope_type、requested_kb_ids、effective_scope_type、effective_kb_ids、is_default_deny_applied 和 isolation_level。
即使换成中文提问，回答范围也只能落在显式声明的单个知识库内。
