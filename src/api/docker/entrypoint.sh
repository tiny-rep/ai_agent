# !/bin/bash

set -e

if [[ "${MIGRATION_ENABLED}" == "true" ]]; then
  echo "Runnable migrations"
  flask --app app.http.app db upgrade
fi

if [[ "${MODE}" == "celery" ]]; then
  # 运行celery
  celery -A app.http.app.celery worker -P ${CELERY_WORKER_CLASS:-prefork} -c ${CELERY_WORKER_AMOUNT:-5} --loglevel INFO

else
  # 5 api环境，判断是生产环境，还是开发环境
  if [[ $"{FLASK_ENV" == "development" ]]; then
    flask run --host=${AIAGENT_BIND_ADDRESS:-0.0.0.0} --port=${AIAGENT_PORT:-5001} --debug
  else
    gunicorn \
      --bind "${AIAGENT_BIND_ADDRESS:-0.0.0.0}:${AIAGENT_PORT:-5001}" \
      --workers ${SERVER_WORKER_AMOUNT:-1} \
      --worker-class ${SERVER_WORKER_CLASS:-gthread} \
      --threads ${SERVER_THREAD_AMOUNT:-2} \
      --timeout ${SERVER_TIMEOUT:-600} \
      --preload \
      app.http.app:app
  fi
fi