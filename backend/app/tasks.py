from datetime import datetime,timezone
from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.models import Deployment,DeploymentLog

@celery_app.task(bind=True,name="deployment.run")
def run_deployment(self,deployment_id:str):
    """Fail closed until a separate isolated BuildKit/gVisor executor is installed."""
    db=SessionLocal()
    try:
        d=db.get(Deployment,deployment_id)
        if not d or d.status in {"CANCELLED","READY"}:return
        d.status="FAILED";d.error_message="Isolated build executor is not installed on this worker; customer source was not executed.";d.finished_at=datetime.now(timezone.utc)
        n=db.query(DeploymentLog).filter_by(deployment_id=d.id).count()+1
        db.add(DeploymentLog(deployment_id=d.id,sequence=n,stream="system",message=d.error_message));db.commit()
    finally:db.close()
