#!/bin/sh
set -eu

install_profile="${INSTALL_PROFILE:-runtime}"
profile="${APP_RUNTIME_MODE:-}"
port="${PORT:-18080}"

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

if [ -z "$profile" ]; then
    case "$install_profile" in
        eval)
            profile="eval"
            ;;
        prod)
            profile="prod"
            ;;
        *)
            profile="api"
            ;;
    esac
fi

case "$profile" in
    prod)
        exec gunicorn             --workers "${GUNICORN_WORKERS:-4}"             --worker-class uvicorn.workers.UvicornWorker             --bind "0.0.0.0:${port}"             api.app:app
        ;;
    api|dev|runtime|full|smoke)
        export KB_API_HOST="${KB_API_HOST:-0.0.0.0}"
        export KB_API_PORT="${KB_API_PORT:-$port}"
        exec python run_api.py
        ;;
    eval)
        exec python scripts/run_chat_eval.py             --cases tests/fixtures/rag_quality/eval_v7/cases.json             --schema tests/fixtures/rag_quality/eval_v7/schema.json             --output-dir temp/eval-v7-docker-check
        ;;
    *)
        echo "Unsupported APP_RUNTIME_MODE: $profile (INSTALL_PROFILE=$install_profile)" >&2
        exit 1
        ;;
esac
