"""本机只读知识库授权令牌管理 CLI。"""

from __future__ import annotations

import argparse
import json

from api.services.access_token_service import access_token_service


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="管理 ThinkRAG 只读知识库令牌")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create", help="创建令牌；明文只显示一次")
    create.add_argument("--name", required=True)
    create.add_argument("--kb", dest="kb_ids", action="append", required=True)
    create.add_argument("--expires-at")
    sub.add_parser("list", help="列出令牌（不含明文和摘要）")
    revoke = sub.add_parser("revoke", help="撤销令牌")
    revoke.add_argument("token_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "create":
        result = access_token_service.create_token(name=args.name, kb_ids=args.kb_ids, expires_at=args.expires_at)
    elif args.command == "list":
        result = {"items": access_token_service.list_tokens()}
    else:
        result = access_token_service.revoke_token(args.token_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
