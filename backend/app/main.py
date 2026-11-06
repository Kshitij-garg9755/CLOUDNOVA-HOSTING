import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI,Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException
from slowapi import Limiter,_rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.core.config import settings,origins,allowed_hosts
from app.core.database import SessionLocal
from app.models import User,HostingPlan
from app.core.security import hash_password
from app.api.routes import router
from app.api.deployments import router as deployments_router

logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(name)s %(message)s")
@asynccontextmanager
async def lifespan(app:FastAPI):
    db=SessionLocal()
    try:
        if db.query(HostingPlan).count()==0:
            for name,price,storage,bandwidth,features in [("Starter",99,20,100,["1 website","Free SSL certificate","Weekly backups","24/7 support"]),("Business",299,100,1000,["Up to 25 websites","Daily backups","Free domain for 1 year","Priority support"]),("Premium",599,250,5000,["Unlimited websites","Advanced security","Staging environment","Dedicated support"]),("Enterprise",1499,1000,20000,["Dedicated resources","Custom infrastructure","99.99% SLA target","Technical account manager"])]:db.add(HostingPlan(name=name,description=f"{name} hosting for your next step.",price_monthly=price,storage_gb=storage,bandwidth_gb=bandwidth,features=features))
            db.commit()
        if settings.bootstrap_admin_email and settings.bootstrap_admin_password:
            admin=db.query(User).filter(User.email==settings.bootstrap_admin_email.lower()).first()
            if not admin:
                db.add(User(name="CloudNova Admin",email=settings.bootstrap_admin_email.lower(),password_hash=hash_password(settings.bootstrap_admin_password),role="admin"));db.commit()
    finally:db.close()
    yield
app=FastAPI(title="CloudNova Hosting API",version="1.0.0",description="Hosting management API. Demo provider responses are explicitly marked.",lifespan=lifespan)
app.state.limiter=Limiter(key_func=get_remote_address,default_limits=["120/minute"])
app.add_exception_handler(RateLimitExceeded,_rate_limit_exceeded_handler)
app.add_middleware(CORSMiddleware,allow_origins=origins(),allow_credentials=True,allow_methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"],allow_headers=["Authorization","Content-Type","X-Razorpay-Signature"])
app.add_middleware(TrustedHostMiddleware,allowed_hosts=allowed_hosts())
@app.middleware("http")
async def secure_headers(request:Request,call_next):
    response=await call_next(request);response.headers["X-Content-Type-Options"]="nosniff";response.headers["X-Frame-Options"]="DENY";response.headers["Referrer-Policy"]="strict-origin-when-cross-origin";response.headers["Permissions-Policy"]="camera=(), microphone=(), geolocation=()";return response
app.include_router(router)
app.include_router(deployments_router)
@app.get("/health")
def health():
    db=SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status":"ok","service":"cloudnova-api","database":"ok"}
    except SQLAlchemyError:
        logging.exception("Database health check failed")
        raise HTTPException(status_code=503,detail="Database unavailable")
    finally:
        db.close()
