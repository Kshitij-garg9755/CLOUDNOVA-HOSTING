import hashlib,hmac,secrets
import logging
from datetime import datetime,timezone
from urllib.parse import quote
from fastapi import APIRouter,Depends,HTTPException,Request,Query
from fastapi.responses import RedirectResponse
from jose import jwt
import httpx
from pydantic import BaseModel,Field
from sqlalchemy.orm import Session
from app.core.config import settings,origins
from app.core.database import get_db
from app.models import User,GitHubInstallation,GitHubRepository,Project,Deployment,DeploymentLog,WebhookEvent,CustomDomain,EnvironmentVariable
from app.api.routes import current_user,admin_user
from app.services.github import GitHubClient,GitHubNotConfigured
from app.services.repository_inspector import inspect_repository,safe_root_directory

router=APIRouter(prefix="/api")
logger=logging.getLogger(__name__)

def _diagnostic_ref(value:str)->str:
    return hashlib.sha256(value.encode()).hexdigest()[:12]
class ProjectCreate(BaseModel):repository_id:str;name:str=Field(min_length=2,max_length=100);branch:str=Field(min_length=1,max_length=120);root_directory:str=".";framework:str|None=None;build_command:str|None=None;install_command:str|None=None;start_command:str|None=None;output_directory:str|None=None;frontend_directory:str|None=None;backend_directory:str|None=None;runtime_version:str|None=None
class ProjectUpdate(BaseModel):name:str|None=None;branch:str|None=None;root_directory:str|None=None;framework:str|None=None;build_command:str|None=None;install_command:str|None=None;start_command:str|None=None;output_directory:str|None=None;frontend_directory:str|None=None;backend_directory:str|None=None;runtime_version:str|None=None;app_port:int|None=Field(default=None,ge=1,le=65535)
class DomainCreate(BaseModel):hostname:str=Field(min_length=4,max_length=253)
class EnvCreate(BaseModel):name:str=Field(pattern=r"^[A-Z_][A-Z0-9_]{0,119}$");value:str=Field(max_length=10000)
def owned_project(project_id:str,db:Session,u:User)->Project:
    p=db.get(Project,project_id)
    if not p or (p.user_id!=u.id and u.role!="admin"):raise HTTPException(404,"Project not found")
    return p
def installation_for(repo:GitHubRepository,db:Session,u:User):
    i=db.get(GitHubInstallation,repo.installation_id)
    if not i or i.status!="active" or not repo.accessible or (i.user_id!=u.id and u.role!="admin"):raise HTTPException(404,"Repository not found")
    return i
def deployment_dict(d):return {"id":d.id,"project_id":d.project_id,"status":d.status,"commit_sha":d.commit_sha,"commit_message":d.commit_message,"live_url":d.live_url,"error_message":d.error_message,"created_at":d.created_at,"started_at":d.started_at,"finished_at":d.finished_at}

@router.get("/github/connect")
def github_connect(request:Request,u:User=Depends(current_user)):
    if not settings.github_app_id or not settings.github_app_slug or not settings.github_private_key_pem:raise HTTPException(503,"GitHub App is not configured on the backend. Set GITHUB_APP_ID, GITHUB_APP_SLUG, GITHUB_PRIVATE_KEY, and GITHUB_CALLBACK_URL in backend/.env locally or the Render service environment, then restart the API.")
    allowed_origins=origins()
    request_origin=(request.headers.get("origin") or "").rstrip("/")
    frontend_origin=request_origin if request_origin in allowed_origins else (allowed_origins[0] if allowed_origins else "")
    state=jwt.encode({"sub":u.id,"purpose":"github_install","frontend_origin":frontend_origin,"exp":datetime.now(timezone.utc).timestamp()+600,"nonce":secrets.token_urlsafe(18)},settings.secret_key,algorithm="HS256")
    return {"url":f"https://github.com/apps/{quote(settings.github_app_slug)}/installations/new?state={quote(state)}","expires_in":600}
@router.get("/github/callback")
def github_callback(installation_id:str|None=None,setup_action:str|None=None,state:str|None=None,db:Session=Depends(get_db)):
    try:
        payload=jwt.decode(state or "",settings.secret_key,algorithms=["HS256"])
        user_id=payload.get("sub") if payload.get("purpose")=="github_install" else None
        frontend_origin=payload.get("frontend_origin")
    except Exception:
        logger.warning("github_installation_callback state=invalid")
        user_id=None;frontend_origin=None
    if not user_id or not installation_id:
        logger.warning("github_installation_callback state=missing_installation_or_user")
        raise HTTPException(400,"GitHub installation state is missing or expired")
    if not frontend_origin or frontend_origin not in origins():
        logger.warning("github_installation_callback user_ref=%s state=frontend_origin_not_allowed",_diagnostic_ref(user_id))
        raise HTTPException(400,"The frontend origin is not allowed. Restart the GitHub connection from the CloudNova website.")
    u=db.get(User,user_id)
    if not u or not u.is_active:raise HTTPException(401,"Account unavailable")
    if not settings.github_app_id or not settings.github_private_key:raise HTTPException(503,"GitHub App credentials are not configured")
    try:
        result=GitHubClient().app_request(f"/app/installations/{installation_id}")
    except httpx.HTTPStatusError as exc:
        logger.warning("github_installation_callback user_ref=%s installation_ref=%s state=github_rejected status=%d request_id=%s",_diagnostic_ref(user_id),_diagnostic_ref(installation_id),exc.response.status_code,exc.response.headers.get("X-GitHub-Request-Id","unknown"))
        raise HTTPException(502,f"GitHub could not verify this installation (HTTP {exc.response.status_code}). Check the GitHub App ID and private key.")
    except Exception as exc:
        logger.warning("github_installation_callback user_ref=%s installation_ref=%s state=verification_error error_type=%s",_diagnostic_ref(user_id),_diagnostic_ref(installation_id),type(exc).__name__)
        raise HTTPException(502,"Could not verify GitHub installation. Check the GitHub App configuration.")
    existing=db.query(GitHubInstallation).filter_by(installation_id=installation_id).first()
    if existing and existing.user_id!=u.id:raise HTTPException(409,"Installation is linked to another account")
    if not existing:
        db.add(GitHubInstallation(user_id=u.id,installation_id=installation_id,account_login=result.get("account",{}).get("login","unknown"),account_type=result.get("account",{}).get("type","Organization"),status="active"))
    else:
        existing.account_login=result.get("account",{}).get("login",existing.account_login);existing.account_type=result.get("account",{}).get("type",existing.account_type);existing.status="active"
    db.commit()
    logger.info("github_installation_callback user_ref=%s installation_ref=%s state=saved account_type=%s",_diagnostic_ref(user_id),_diagnostic_ref(installation_id),result.get("account",{}).get("type","unknown"))
    # Redirect to the signed-in project area; installation metadata is not placed in the URL.
    return RedirectResponse(frontend_origin+"/dashboard/projects?github=connected",status_code=303)

@router.get("/github/status")
def github_status(db:Session=Depends(get_db),u:User=Depends(current_user)):
    installations=db.query(GitHubInstallation).filter_by(user_id=u.id).all()
    active=[item for item in installations if item.status=="active"]
    logger.info("github_status user_ref=%s active_installations=%d",_diagnostic_ref(u.id),len(active))
    return {
        "app_configured":bool(settings.github_app_id and settings.github_app_slug and settings.github_private_key_pem),
        "callback_configured":bool(settings.github_callback_url),
        "active_installation_count":len(active),
        "installations":[{
            "account_login":item.account_login,
            "status":item.status,
            "accessible_repository_count":db.query(GitHubRepository).filter_by(installation_id=item.id,accessible=True).count(),
        } for item in installations],
    }

@router.get("/github/repositories")
def github_repositories(db:Session=Depends(get_db),u:User=Depends(current_user)):
    installations=db.query(GitHubInstallation).filter_by(user_id=u.id,status="active").all();result=[]
    logger.info("github_repository_list_started user_ref=%s active_installations=%d",_diagnostic_ref(u.id),len(installations))
    if not installations:
        logger.warning("github_repository_list_empty user_ref=%s reason=no_active_installation",_diagnostic_ref(u.id))
    for i in installations:
        try:
            repos=GitHubClient().installation_repositories(i.installation_id)
            cached=db.query(GitHubRepository).filter_by(installation_id=i.id).all()
            for old in cached:old.accessible=False
            for r in repos:
                if not isinstance(r,dict) or not r.get("id") or not r.get("full_name"):continue
                row=db.query(GitHubRepository).filter_by(installation_id=i.id,github_repo_id=str(r["id"])).first()
                owner=r.get("owner",{}).get("login") or r["full_name"].split("/",1)[0]
                if not row:row=GitHubRepository(installation_id=i.id,github_repo_id=str(r["id"]),full_name=r["full_name"],owner=owner,description=r.get("description"),private=r.get("private",True),default_branch=r.get("default_branch","main"),accessible=True);db.add(row)
                else:row.full_name=r["full_name"];row.owner=owner;row.description=r.get("description");row.private=r.get("private",True);row.default_branch=r.get("default_branch","main");row.accessible=True
                result.append(row)
        except GitHubNotConfigured:
            logger.error("github_repository_list_failed user_ref=%s installation_ref=%s reason=app_not_configured",_diagnostic_ref(u.id),_diagnostic_ref(i.installation_id))
            raise HTTPException(503,"GitHub App is not configured on the API service.")
        except httpx.HTTPStatusError as exc:
            status=exc.response.status_code
            logger.warning("github_repository_list_failed user_ref=%s installation_ref=%s status=%d request_id=%s",_diagnostic_ref(u.id),_diagnostic_ref(i.installation_id),status,exc.response.headers.get("X-GitHub-Request-Id","unknown"))
            if status in {401,403}:
                detail=f"GitHub denied repository access (HTTP {status}). Check the App installation selection and Metadata read permission."
            elif status==404:
                detail="GitHub could not find the saved installation. Reconnect the GitHub App from this CloudNova account."
            else:
                detail=f"GitHub repository request failed (HTTP {status}). Retry, then check the GitHub App configuration if it continues."
            raise HTTPException(502,detail)
        except Exception as exc:
            logger.warning("github_repository_list_failed user_ref=%s installation_ref=%s error_type=%s",_diagnostic_ref(u.id),_diagnostic_ref(i.installation_id),type(exc).__name__)
            raise HTTPException(502,"GitHub repository listing failed. Check the API logs using the request time; no credentials are included there.")
    db.commit()
    logger.info("github_repository_list_completed user_ref=%s active_installations=%d repository_count=%d",_diagnostic_ref(u.id),len(installations),len(result))
    return {"items":[{"id":r.id,"github_repo_id":int(r.github_repo_id),"name":r.full_name.rsplit("/",1)[-1],"owner":r.owner or r.full_name.split("/",1)[0],"full_name":r.full_name,"visibility":"private" if r.private else "public","private":r.private,"description":r.description,"default_branch":r.default_branch} for r in result]}
@router.get("/github/repositories/{repository_id}")
def github_repository_details(repository_id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    repo=db.get(GitHubRepository,repository_id)
    if not repo:raise HTTPException(404,"Repository not found")
    installation=installation_for(repo,db,u)
    try:
        r=GitHubClient().request(installation.installation_id,f"/repos/{repo.full_name}")
    except Exception:raise HTTPException(502,"GitHub repository details could not be loaded")
    repo.default_branch=r.get("default_branch",repo.default_branch);repo.private=r.get("private",repo.private);db.commit()
    repo.owner=r.get("owner",{}).get("login") or repo.owner;repo.description=r.get("description");db.commit()
    return {"id":repo.id,"github_repo_id":int(repo.github_repo_id),"name":repo.full_name.rsplit("/",1)[-1],"owner":repo.owner or repo.full_name.split("/",1)[0],"full_name":repo.full_name,"private":repo.private,"visibility":"private" if repo.private else "public","default_branch":repo.default_branch,"html_url":r.get("html_url"),"description":repo.description,"installation_status":installation.status}
@router.get("/github/repositories/{repository_id}/branches")
def github_branches(repository_id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    repo=db.get(GitHubRepository,repository_id)
    if not repo:raise HTTPException(404,"Repository not found")
    i=installation_for(repo,db,u)
    try:data=GitHubClient().request(i.installation_id,f"/repos/{repo.full_name}/branches",{"per_page":100})
    except Exception:raise HTTPException(502,"GitHub branch listing failed")
    return {"items":[{"name":b["name"],"protected":b.get("protected",False)} for b in data]}
@router.get("/github/repositories/{repository_id}/detect")
def github_detect(repository_id:str,branch:str|None=None,root_directory:str=".",db:Session=Depends(get_db),u:User=Depends(current_user)):
    repo=db.get(GitHubRepository,repository_id)
    if not repo:raise HTTPException(404,"Repository not found")
    installation=installation_for(repo,db,u)
    selected_branch=branch or repo.default_branch
    try:
        return inspect_repository(GitHubClient(),installation.installation_id,repo.full_name,selected_branch,root_directory)
    except ValueError as exc:raise HTTPException(422,str(exc))
    except GitHubNotConfigured:raise HTTPException(503,"GitHub App is not configured")
    except Exception:raise HTTPException(502,"Could not detect project settings from the selected branch")
@router.post("/github/disconnect")
def github_disconnect(db:Session=Depends(get_db),u:User=Depends(current_user)):
    rows=db.query(GitHubInstallation).filter_by(user_id=u.id,status="active").all()
    for i in rows:
        i.status="revoked"
        for repo in db.query(GitHubRepository).filter_by(installation_id=i.id).all():repo.accessible=False
    db.commit();return {"revoked_installations":len(rows),"project_history_preserved":True}

@router.post("/projects",status_code=201)
def create_project(data:ProjectCreate,db:Session=Depends(get_db),u:User=Depends(current_user)):
    repo=db.get(GitHubRepository,data.repository_id)
    if not repo:raise HTTPException(404,"Repository not found; refresh the authorized repository list")
    installation_for(repo,db,u)
    if db.query(Project).filter_by(repository_id=repo.id,name=data.name).first():raise HTTPException(409,"Project already exists for this repository")
    try:
        root=safe_root_directory(data.root_directory)
        inst=db.get(GitHubInstallation,repo.installation_id)
        detection=inspect_repository(GitHubClient(),inst.installation_id,repo.full_name,data.branch,root)
    except GitHubNotConfigured:raise HTTPException(503,"GitHub App is not configured")
    except ValueError as exc:raise HTTPException(422,str(exc))
    except Exception:raise HTTPException(422,"Could not inspect repository branch")
    values={**detection,"framework":data.framework or detection.get("framework"),"install_command":data.install_command if data.install_command is not None else detection.get("install_command"),"build_command":data.build_command if data.build_command is not None else detection.get("build_command"),"start_command":data.start_command if data.start_command is not None else detection.get("start_command"),"output_directory":data.output_directory if data.output_directory is not None else detection.get("output_directory"),"runtime_version":data.runtime_version or detection.get("runtime_version")}
    slug="".join(c.lower() if c.isalnum() else "-" for c in data.name).strip("-")[:70] or "project";slug=f"{slug}-{secrets.token_hex(3)}"
    p=Project(user_id=u.id,repository_id=repo.id,name=data.name,slug=slug,branch=data.branch,root_directory=root or ".",frontend_directory=data.frontend_directory,backend_directory=data.backend_directory,**values);db.add(p);db.commit();db.refresh(p)
    return project_dict(p,repo)
def project_dict(p,repo=None):return {"id":p.id,"name":p.name,"slug":p.slug,"repository_id":p.repository_id,"repository":repo.full_name if repo else None,"branch":p.branch,"framework":p.framework,"root_directory":p.root_directory,"frontend_directory":p.frontend_directory,"backend_directory":p.backend_directory,"install_command":p.install_command,"build_command":p.build_command,"start_command":p.start_command,"output_directory":p.output_directory,"runtime_version":p.runtime_version,"app_port":p.app_port,"created_at":p.created_at}
@router.get("/projects")
def list_projects(db:Session=Depends(get_db),u:User=Depends(current_user),limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
    q=db.query(Project).filter(Project.user_id==u.id);rows=q.order_by(Project.created_at.desc()).offset(offset).limit(limit).all();return {"items":[project_dict(p,db.get(GitHubRepository,p.repository_id)) for p in rows],"total":q.count()}
@router.get("/projects/{project_id}")
def get_project(project_id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    p=owned_project(project_id,db,u);return project_dict(p,db.get(GitHubRepository,p.repository_id))
@router.put("/projects/{project_id}")
def update_project(project_id:str,data:ProjectUpdate,db:Session=Depends(get_db),u:User=Depends(current_user)):
    p=owned_project(project_id,db,u)
    for k,v in data.model_dump(exclude_unset=True).items():setattr(p,k,v)
    db.commit();return project_dict(p,db.get(GitHubRepository,p.repository_id))
@router.delete("/projects/{project_id}")
def delete_project(project_id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    p=owned_project(project_id,db,u);db.delete(p);db.commit();return {"deleted":True}

@router.post("/projects/{project_id}/deploy",status_code=202)
def deploy_project(project_id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    p=owned_project(project_id,db,u)
    if not settings.deployment_worker_enabled or settings.deployment_isolation_runtime!="runsc":raise HTTPException(503,"Isolated deployment worker is not configured. Configure a dedicated gVisor (runsc) worker before accepting customer builds.")
    # The control plane never executes customer code. Queue integration is enabled only when a worker is deployed.
    try:
        from app.tasks import run_deployment
        d=Deployment(project_id=p.id,user_id=u.id,status="QUEUED");db.add(d);db.commit();db.refresh(d);run_deployment.delay(d.id)
        return deployment_dict(d)
    except Exception as e:
        db.rollback()
        if "d" in locals() and d.id:
            failed=db.get(Deployment,d.id)
            if failed:
                failed.status="FAILED";failed.error_message="Deployment queue unavailable; customer source was not executed.";failed.finished_at=datetime.now(timezone.utc)
                db.add(DeploymentLog(deployment_id=failed.id,sequence=1,stream="system",message=failed.error_message));db.commit()
        raise HTTPException(503,"Deployment queue unavailable; no customer code was executed") from e
@router.get("/projects/{project_id}/deployments")
def project_deployments(project_id:str,db:Session=Depends(get_db),u:User=Depends(current_user),limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
    p=owned_project(project_id,db,u);q=db.query(Deployment).filter_by(project_id=p.id);rows=q.order_by(Deployment.created_at.desc()).offset(offset).limit(limit).all();return {"items":[deployment_dict(d) for d in rows],"total":q.count()}
@router.get("/deployments/{deployment_id}")
def get_deployment(deployment_id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    d=db.get(Deployment,deployment_id)
    if not d or (d.user_id!=u.id and u.role!="admin"):raise HTTPException(404,"Deployment not found")
    return deployment_dict(d)
@router.get("/deployments/{deployment_id}/logs")
def deployment_logs(deployment_id:str,db:Session=Depends(get_db),u:User=Depends(current_user),limit:int=Query(500,ge=1,le=2000)):
    d=db.get(Deployment,deployment_id)
    if not d or (d.user_id!=u.id and u.role!="admin"):raise HTTPException(404,"Deployment not found")
    rows=db.query(DeploymentLog).filter_by(deployment_id=d.id).order_by(DeploymentLog.sequence).limit(limit).all();return {"items":[{"sequence":x.sequence,"stream":x.stream,"message":x.message,"created_at":x.created_at} for x in rows]}
@router.post("/deployments/{deployment_id}/cancel")
def cancel_deployment(deployment_id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    d=db.get(Deployment,deployment_id)
    if not d or (d.user_id!=u.id and u.role!="admin"):raise HTTPException(404,"Deployment not found")
    if d.status not in {"QUEUED","CLONING","INSTALLING","BUILDING","UPLOADING","DEPLOYING","HEALTH_CHECK"}:raise HTTPException(409,"Deployment cannot be cancelled in its current state")
    d.status="CANCELLED";d.finished_at=datetime.now(timezone.utc);db.commit();return deployment_dict(d)
@router.post("/deployments/{deployment_id}/rollback")
def rollback_deployment(deployment_id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    d=db.get(Deployment,deployment_id)
    if not d or (d.user_id!=u.id and u.role!="admin"):raise HTTPException(404,"Deployment not found")
    raise HTTPException(503,"Rollback requires an active artifact storage and atomic routing provider")

@router.post("/webhooks/github")
async def github_webhook(request:Request,db:Session=Depends(get_db)):
    body=await request.body();sig=request.headers.get("x-hub-signature-256","");delivery=request.headers.get("x-github-delivery","");event=request.headers.get("x-github-event","")
    if not settings.github_webhook_secret:raise HTTPException(503,"GitHub webhook secret is not configured")
    expected="sha256="+hmac.new(settings.github_webhook_secret.encode(),body,hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig,expected):raise HTTPException(401,"Invalid webhook signature")
    if not delivery:raise HTTPException(400,"Missing GitHub delivery id")
    old=db.query(WebhookEvent).filter_by(delivery_id=delivery).first()
    if old:return {"accepted":True,"duplicate":True}
    import json
    try:payload=json.loads(body)
    except (ValueError,UnicodeDecodeError):raise HTTPException(400,"Invalid webhook JSON")
    installation_id=str(payload.get("installation",{}).get("id") or "")
    row=WebhookEvent(delivery_id=delivery,event_type=event,installation_id=installation_id or None,processed=False);db.add(row);db.flush()
    installation=db.query(GitHubInstallation).filter_by(installation_id=installation_id).first() if installation_id else None
    if event=="installation" and installation:
        action=payload.get("action")
        status_map={"created":"active","unsuspend":"active","deleted":"revoked","suspend":"suspended"}
        if action in status_map:
            installation.status=status_map[action]
            if installation.status!="active":
                for repo_row in db.query(GitHubRepository).filter_by(installation_id=installation.id).all():repo_row.accessible=False
    if event=="installation_repositories" and installation:
        action=payload.get("action")
        if action=="removed":
            removed={str(x.get("id")) for x in payload.get("repositories_removed",[])}
            for repo_row in db.query(GitHubRepository).filter_by(installation_id=installation.id).all():
                if repo_row.github_repo_id in removed:repo_row.accessible=False
        elif action=="added":
            try:
                data=GitHubClient().request(installation.installation_id,"/installation/repositories",{"per_page":100})
                available={str(x["id"]):x for x in data.get("repositories",[])}
                for repo_row in db.query(GitHubRepository).filter_by(installation_id=installation.id).all():
                    if repo_row.github_repo_id in available:repo_row.accessible=True
                for github_id,r in available.items():
                    repo_row=db.query(GitHubRepository).filter_by(installation_id=installation.id,github_repo_id=github_id).first()
                    if not repo_row:db.add(GitHubRepository(installation_id=installation.id,github_repo_id=github_id,full_name=r["full_name"],private=r.get("private",True),default_branch=r.get("default_branch","main"),accessible=True))
            except Exception:
                db.rollback();raise HTTPException(503,"Could not synchronize newly authorized repositories")
    if event=="push":
        full_name=payload.get("repository",{}).get("full_name");branch=(payload.get("ref") or "").removeprefix("refs/heads/");sha=payload.get("after");message=(payload.get("head_commit") or {}).get("message")
        repo=db.query(GitHubRepository).filter_by(full_name=full_name,accessible=True).join(GitHubInstallation,GitHubRepository.installation_id==GitHubInstallation.id).filter(GitHubInstallation.installation_id==installation_id,GitHubInstallation.status=="active").first()
        projects=db.query(Project).filter_by(repository_id=repo.id,branch=branch).all() if repo else []
        dispatch_ids=[]
        for p in projects:
            d=Deployment(project_id=p.id,user_id=p.user_id,status="QUEUED",commit_sha=sha,commit_message=message);db.add(d);db.flush()
            db.add(DeploymentLog(deployment_id=d.id,sequence=1,stream="system",message="Push received and signature verified. Waiting for an isolated deployment worker."))
            dispatch_ids.append(d.id)
    else:dispatch_ids=[]
    row.processed=True;db.commit()
    if event=="push" and dispatch_ids:
        if not settings.deployment_worker_enabled or settings.deployment_isolation_runtime!="runsc":
            for deployment_id in dispatch_ids:
                d=db.get(Deployment,deployment_id);d.status="FAILED";d.error_message="No isolated gVisor deployment worker is configured; source was not executed.";d.finished_at=datetime.now(timezone.utc)
                db.add(DeploymentLog(deployment_id=d.id,sequence=2,stream="system",message=d.error_message))
            db.commit()
        else:
            try:
                from app.tasks import run_deployment
                for deployment_id in dispatch_ids:run_deployment.delay(deployment_id)
            except Exception:
                for deployment_id in dispatch_ids:
                    d=db.get(Deployment,deployment_id);d.status="FAILED";d.error_message="Deployment queue is unavailable; source was not executed.";d.finished_at=datetime.now(timezone.utc)
                db.commit()
    return {"accepted":True,"duplicate":False,"matched_projects":len(dispatch_ids)}

@router.post("/projects/{project_id}/domains",status_code=201)
def add_domain(project_id:str,data:DomainCreate,db:Session=Depends(get_db),u:User=Depends(current_user)):
    p=owned_project(project_id,db,u);host=data.hostname.lower().rstrip(".")
    if not all(part and len(part)<=63 and part[0].isalnum() and part[-1].isalnum() and all(c.isalnum() or c=="-" for c in part) for part in host.split(".")):raise HTTPException(422,"Invalid hostname")
    if db.query(CustomDomain).filter_by(hostname=host).first():raise HTTPException(409,"Hostname is already registered")
    d=CustomDomain(project_id=p.id,hostname=host,verification_token=secrets.token_urlsafe(24));db.add(d);db.commit();db.refresh(d)
    return {"id":d.id,"hostname":d.hostname,"status":d.status,"verified":False,"dns_instructions":{"type":"TXT","name":f"_cloudnova-verification.{host}","value":d.verification_token}}
@router.get("/projects/{project_id}/domains")
def list_domains(project_id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    p=owned_project(project_id,db,u);return {"items":[{"id":d.id,"hostname":d.hostname,"status":d.status,"verified":d.verified} for d in db.query(CustomDomain).filter_by(project_id=p.id).all()]}
@router.post("/domains/{domain_id}/verify")
def verify_domain(domain_id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    d=db.get(CustomDomain,domain_id)
    if not d or owned_project(d.project_id,db,u).user_id!=u.id:raise HTTPException(404,"Domain not found")
    try:
        import dns.resolver
        records=dns.resolver.resolve(f"_cloudnova-verification.{d.hostname}","TXT",lifetime=5)
        expected=d.verification_token
        if not any(expected in "".join(x.decode() for x in r.strings) for r in records):return {"verified":False,"status":"pending_dns","message":"Verification TXT record was not found yet."}
    except ImportError:raise HTTPException(503,"DNS verification dependency is unavailable")
    except Exception:return {"verified":False,"status":"pending_dns","message":"TXT record not found or DNS still propagating."}
    d.verified=True;d.status="verified_ssl_not_configured";db.commit();return {"verified":True,"status":d.status,"message":"Domain ownership verified. SSL remains inactive until ACME routing is configured."}
@router.delete("/domains/{domain_id}")
def delete_domain(domain_id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    d=db.get(CustomDomain,domain_id)
    if not d or owned_project(d.project_id,db,u).user_id!=u.id:raise HTTPException(404,"Domain not found")
    db.delete(d);db.commit();return {"deleted":True}

def cipher():
    from cryptography.fernet import Fernet
    import base64
    key=base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode()).digest());return Fernet(key)
@router.get("/projects/{project_id}/environment")
def list_env(project_id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    p=owned_project(project_id,db,u);return {"items":[{"id":x.id,"name":x.name,"value_set":True} for x in db.query(EnvironmentVariable).filter_by(project_id=p.id).all()]}
@router.post("/projects/{project_id}/environment",status_code=201)
def create_env(project_id:str,data:EnvCreate,db:Session=Depends(get_db),u:User=Depends(current_user)):
    p=owned_project(project_id,db,u)
    if db.query(EnvironmentVariable).filter_by(project_id=p.id,name=data.name).first():raise HTTPException(409,"Variable already exists")
    x=EnvironmentVariable(project_id=p.id,name=data.name,encrypted_value=cipher().encrypt(data.value.encode()).decode());db.add(x);db.commit();return {"id":x.id,"name":x.name,"value_set":True}
@router.put("/environment/{variable_id}")
def update_env(variable_id:str,data:EnvCreate,db:Session=Depends(get_db),u:User=Depends(current_user)):
    x=db.get(EnvironmentVariable,variable_id)
    if not x or owned_project(x.project_id,db,u).user_id!=u.id:raise HTTPException(404,"Variable not found")
    x.name=data.name;x.encrypted_value=cipher().encrypt(data.value.encode()).decode();db.commit();return {"id":x.id,"name":x.name,"value_set":True}
@router.delete("/environment/{variable_id}")
def delete_env(variable_id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    x=db.get(EnvironmentVariable,variable_id)
    if not x or owned_project(x.project_id,db,u).user_id!=u.id:raise HTTPException(404,"Variable not found")
    db.delete(x);db.commit();return {"deleted":True}

@router.get("/projects/{project_id}/runtime")
def project_runtime(project_id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    owned_project(project_id,db,u);return {"status":"not_configured","message":"No isolated runtime provider is configured; no application is running."}
@router.post("/projects/{project_id}/runtime/{action}")
def runtime_action(project_id:str,action:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    owned_project(project_id,db,u)
    if action not in {"start","stop","restart"}:raise HTTPException(404,"Unknown runtime action")
    raise HTTPException(503,"Runtime control is unavailable until isolated runtime orchestration is configured")
@router.get("/admin/deployments")
def admin_deployments(db:Session=Depends(get_db),_:User=Depends(admin_user),status:str|None=None,limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
    q=db.query(Deployment)
    if status:q=q.filter_by(status=status)
    rows=q.order_by(Deployment.created_at.desc()).offset(offset).limit(limit).all();return {"items":[deployment_dict(d) for d in rows],"total":q.count()}
@router.get("/admin/workers")
def admin_workers(_:User=Depends(admin_user)):return {"items":[],"status":"no_workers_registered","isolation_runtime":settings.deployment_isolation_runtime or None}
@router.get("/admin/domains")
def admin_domains(db:Session=Depends(get_db),_:User=Depends(admin_user),limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
    q=db.query(CustomDomain);rows=q.offset(offset).limit(limit).all();return {"items":[{"id":x.id,"project_id":x.project_id,"hostname":x.hostname,"status":x.status,"verified":x.verified} for x in rows],"total":q.count()}
@router.get("/admin/usage")
def admin_usage(db:Session=Depends(get_db),_:User=Depends(admin_user)):
    from app.models import ResourceUsage
    return {"items":[{"user_id":x.user_id,"project_id":x.project_id,"metric":x.metric,"value":x.value,"unit":x.unit,"created_at":x.created_at} for x in db.query(ResourceUsage).order_by(ResourceUsage.created_at.desc()).limit(100).all()]}
