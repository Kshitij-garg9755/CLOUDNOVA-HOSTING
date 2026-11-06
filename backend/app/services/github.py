import time
import httpx
from jose import jwt
from app.core.config import settings

API="https://api.github.com"
class GitHubNotConfigured(RuntimeError):pass
class GitHubClient:
    def __init__(self):
        if not settings.github_app_id or not settings.github_private_key:raise GitHubNotConfigured("GitHub App credentials are not configured")
        self.key=settings.github_private_key_pem
    def app_token(self):
        now=int(time.time());return jwt.encode({"iat":now-30,"exp":now+540,"iss":settings.github_app_id},self.key,algorithm="RS256")
    def installation_token(self,installation_id:str)->str:
        r=httpx.post(f"{API}/app/installations/{installation_id}/access_tokens",headers={"Authorization":f"Bearer {self.app_token()}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"},timeout=15)
        r.raise_for_status();return r.json()["token"]
    def app_request(self,path:str):
        r=httpx.get(f"{API}{path}",headers={"Authorization":f"Bearer {self.app_token()}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"},timeout=15);r.raise_for_status();return r.json()
    def request(self,installation_id:str,path:str,params=None):
        r=httpx.get(f"{API}{path}",params=params,headers={"Authorization":f"Bearer {self.installation_token(installation_id)}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"},timeout=20);r.raise_for_status();return r.json()
    def installation_repositories(self,installation_id:str)->list[dict]:
        """Fetch all repositories currently selected for this App installation."""
        repositories=[]
        for page in range(1,101):
            result=self.request(installation_id,"/installation/repositories",{"per_page":100,"page":page})
            batch=result.get("repositories",[])
            if not isinstance(batch,list):raise ValueError("GitHub returned an invalid repository list")
            repositories.extend(batch)
            if len(batch)<100:break
        return repositories
