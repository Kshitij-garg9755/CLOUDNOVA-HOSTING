import hashlib
import logging
import time
import httpx
from jose import jwt
from app.core.config import settings

API="https://api.github.com"
logger=logging.getLogger(__name__)
class GitHubNotConfigured(RuntimeError):pass

def _installation_ref(installation_id:str)->str:
    return hashlib.sha256(installation_id.encode()).hexdigest()[:12]

class GitHubClient:
    def __init__(self):
        if not settings.github_app_id or not settings.github_private_key:raise GitHubNotConfigured("GitHub App credentials are not configured")
        self.key=settings.github_private_key_pem
    def app_token(self):
        now=int(time.time());return jwt.encode({"iat":now-30,"exp":now+540,"iss":settings.github_app_id},self.key,algorithm="RS256")
    def installation_token(self,installation_id:str)->str:
        r=httpx.post(f"{API}/app/installations/{installation_id}/access_tokens",headers={"Authorization":f"Bearer {self.app_token()}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"},timeout=15)
        try:r.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning("github_api_error operation=installation_token installation_ref=%s status=%d request_id=%s",_installation_ref(installation_id),exc.response.status_code,exc.response.headers.get("X-GitHub-Request-Id","unknown"))
            raise
        return r.json()["token"]
    def app_request(self,path:str):
        r=httpx.get(f"{API}{path}",headers={"Authorization":f"Bearer {self.app_token()}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"},timeout=15)
        try:r.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning("github_api_error operation=app_request status=%d request_id=%s",exc.response.status_code,exc.response.headers.get("X-GitHub-Request-Id","unknown"))
            raise
        return r.json()
    def request(self,installation_id:str,path:str,params=None):
        r=httpx.get(f"{API}{path}",params=params,headers={"Authorization":f"Bearer {self.installation_token(installation_id)}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"},timeout=20)
        try:r.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning("github_api_error operation=installation_request installation_ref=%s endpoint=%s status=%d request_id=%s",_installation_ref(installation_id),path,exc.response.status_code,exc.response.headers.get("X-GitHub-Request-Id","unknown"))
            raise
        return r.json()
    def installation_repositories(self,installation_id:str)->list[dict]:
        """Fetch all repositories currently selected for this App installation."""
        repositories=[]
        page=1
        while True:
            result=self.request(installation_id,"/installation/repositories",{"per_page":100,"page":page})
            batch=result.get("repositories",[])
            if not isinstance(batch,list):raise ValueError("GitHub returned an invalid repository list")
            repositories.extend(batch)
            total=result.get("total_count")
            logger.info("github_repository_page installation_ref=%s page=%d count=%d total=%s",_installation_ref(installation_id),page,len(batch),total if isinstance(total,int) else "unknown")
            if (isinstance(total,int) and len(repositories)>=total) or len(batch)<100:break
            page+=1
        return repositories
