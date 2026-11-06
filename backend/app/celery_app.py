from celery import Celery
from app.core.config import settings
celery_app=Celery("cloudnova",broker=settings.redis_url,backend=settings.redis_url,include=["app.tasks"])
celery_app.conf.update(task_acks_late=True,task_reject_on_worker_lost=True,worker_prefetch_multiplier=1,task_soft_time_limit=60,task_time_limit=90,task_serializer="json",result_serializer="json",accept_content=["json"])
