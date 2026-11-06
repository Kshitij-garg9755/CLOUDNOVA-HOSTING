import base64
import hashlib
import hmac
import json
from urllib.parse import parse_qs,urlparse
from app.core.config import settings
from app.core.database import SessionLocal
from app.models import User, GitHubInstallation

def auth(client):
    client.post("/api/auth/register",json={"name":"GitHub User","email":"gh@example.com","password":"secure-pass-123"})
    token=client.post("/api/auth/login",data={"username":"gh@example.com","password":"secure-pass-123"}).json()["access_token"]
    return {"Authorization":f"Bearer {token}"}

def add_installation():
    db=SessionLocal()
    try:
        user=db.query(User).filter_by(email="gh@example.com").one()
        row=GitHubInstallation(user_id=user.id,installation_id="7766",account_login="cloudnova-test",account_type="Organization")
        db.add(row);db.commit();db.refresh(row);return row.id
    finally:db.close()

def test_github_app_jwt_is_signed_with_configured_pem(monkeypatch):
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    from jose import jwt
    private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    pem=private.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()).decode()
    monkeypatch.setattr(settings,"github_app_id","12345");monkeypatch.setattr(settings,"github_private_key",pem.replace("\n","\\n"))
    from app.services.github import GitHubClient
    token=GitHubClient().app_token();payload=jwt.decode(token,private.public_key(),algorithms=["RS256"])
    assert payload["iss"]=="12345"

def test_installation_callback_saves_id_and_returns_to_origin_that_started_flow(client,monkeypatch):
    from app.core.config import settings
    from app.services.github import GitHubClient
    headers=auth(client)
    monkeypatch.setattr(settings,"github_app_id","12345");monkeypatch.setattr(settings,"github_app_slug","cloudnova-test")
    monkeypatch.setattr(settings,"github_private_key","test-key")
    monkeypatch.setattr(settings,"frontend_origins","http://localhost:5173,https://cloudnova-test.netlify.app")
    connected=client.get("/api/github/connect",headers={**headers,"Origin":"https://cloudnova-test.netlify.app"})
    state=parse_qs(urlparse(connected.json()["url"]).query)["state"][0]
    monkeypatch.setattr(GitHubClient,"app_request",lambda self,path:{"account":{"login":"cloudnova-test","type":"Organization"}})
    response=client.get("/api/github/callback",params={"installation_id":"7766","setup_action":"install","state":state},follow_redirects=False)
    assert response.status_code==303
    assert response.headers["location"]=="https://cloudnova-test.netlify.app/dashboard/projects?github=connected"
    db=SessionLocal()
    try:
        row=db.query(GitHubInstallation).filter_by(installation_id="7766").one()
        assert row.account_login=="cloudnova-test" and row.status=="active"
    finally:db.close()

def test_installation_repository_listing_and_branch_selection(client,monkeypatch):
    headers=auth(client);add_installation()
    monkeypatch.setattr(settings,"github_app_id","test-app-id");monkeypatch.setattr(settings,"github_private_key","test-key")
    status=client.get("/api/github/status",headers=headers)
    assert status.status_code==200 and status.json()["active_installation_count"]==1
    assert status.json()["installations"][0]["account_login"]=="cloudnova-test"
    assert "installation_id" not in status.json()["installations"][0]
    assert "private_key" not in status.json()
    def fake_request(self,installation_id,path,params=None):
        if path=="/installation/repositories":return {"repositories":[{"id":991,"full_name":"cloudnova-test/site","owner":{"login":"cloudnova-test"},"description":"Private app","private":True,"default_branch":"trunk"},{"id":992,"full_name":"cloudnova-test/public-site","owner":{"login":"cloudnova-test"},"description":"Public site","private":False,"default_branch":"main"}]}
        if path.endswith("/branches"):return [{"name":"trunk","protected":True},{"name":"preview","protected":False}]
        if path=="/repos/cloudnova-test/site":return {"default_branch":"trunk","private":True,"html_url":"https://github.com/cloudnova-test/site","description":"Site"}
        if path=="/repos/cloudnova-test/site/contents":return [{"name":"package.json","path":"package.json","type":"file"}]
        if path=="/repos/cloudnova-test/site/contents/package.json":return {"content":base64.b64encode(b'{"dependencies":{"react":"*","vite":"*"}}').decode()}
        raise AssertionError(path)
    monkeypatch.setattr("app.api.deployments.GitHubClient.request",fake_request)
    repos=client.get("/api/github/repositories",headers=headers);assert repos.status_code==200
    repository_id=repos.json()["items"][0]["id"]
    listed=repos.json()["items"][0]
    assert listed["github_repo_id"]==991 and listed["name"]=="site"
    assert listed["full_name"]=="cloudnova-test/site" and listed["default_branch"]=="trunk"
    assert listed["owner"]=="cloudnova-test" and listed["description"]=="Private app"
    assert listed["private"] is True and listed["visibility"]=="private"
    public=next(item for item in repos.json()["items"] if item["github_repo_id"]==992)
    assert public["name"]=="public-site" and public["private"] is False and public["visibility"]=="public"
    details=client.get(f"/api/github/repositories/{repository_id}",headers=headers);assert details.json()["default_branch"]=="trunk"
    detected=client.get(f"/api/github/repositories/{repository_id}/detect",params={"branch":"trunk"},headers=headers)
    assert detected.status_code==200 and detected.json()["framework"]=="React + Vite"
    branches=client.get(f"/api/github/repositories/{repository_id}/branches",headers=headers)
    assert [b["name"] for b in branches.json()["items"]]==["trunk","preview"]
    monkeypatch.setattr("app.api.deployments.inspect_repository",lambda *args:{"framework":"React + Vite","install_command":"npm ci","build_command":"npm run build","output_directory":"dist","runtime_version":"20"})
    imported=client.post("/api/projects",headers=headers,json={"repository_id":repository_id,"name":"CloudNova Site","branch":"trunk","root_directory":"frontend","framework":"React + Vite","install_command":"npm ci","build_command":"npm run build","output_directory":"dist","runtime_version":"20"})
    assert imported.status_code==201
    assert imported.json()["root_directory"]=="frontend" and imported.json()["framework"]=="React + Vite"
    assert imported.json()["install_command"]=="npm ci" and imported.json()["output_directory"]=="dist"
    project_id=imported.json()["id"]
    saved=client.post(f"/api/projects/{project_id}/environment",headers=headers,json={"name":"BUILD_SECRET","value":"private-test-value"})
    assert saved.status_code==201 and "value" not in saved.json()
    listed=client.get(f"/api/projects/{project_id}/environment",headers=headers)
    assert listed.json()["items"]==[{"id":saved.json()["id"],"name":"BUILD_SECRET","value_set":True}]

def test_repository_listing_reports_permission_failure_without_logging_credentials(client,monkeypatch,caplog):
    import httpx
    from app.services.github import GitHubClient
    headers=auth(client);add_installation()
    monkeypatch.setattr(settings,"github_app_id","test-app-id");monkeypatch.setattr(settings,"github_private_key","never-log-this-private-key")
    response=httpx.Response(403,request=httpx.Request("GET","https://api.github.com/installation/repositories"),headers={"X-GitHub-Request-Id":"safe-request-ref"})
    failure=httpx.HTTPStatusError("forbidden",request=response.request,response=response)
    monkeypatch.setattr(GitHubClient,"installation_repositories",lambda self,installation_id:(_ for _ in ()).throw(failure))
    result=client.get("/api/github/repositories",headers=headers)
    assert result.status_code==502 and "HTTP 403" in result.json()["detail"]
    assert "never-log-this-private-key" not in caplog.text and "Bearer" not in caplog.text
    assert "safe-request-ref" in caplog.text

def test_installation_repository_listing_fetches_all_pages(monkeypatch):
    from app.services.github import GitHubClient
    requested=[]
    def fake_request(self,installation_id,path,params=None):
        requested.append(params["page"])
        if params["page"]==1:return {"repositories":[{"id":i,"full_name":f"org/repo-{i}"} for i in range(100)]}
        return {"repositories":[{"id":101,"full_name":"org/repo-101"}]}
    monkeypatch.setattr(GitHubClient,"request",fake_request)
    repositories=GitHubClient.__new__(GitHubClient).installation_repositories("7766")
    assert len(repositories)==101 and requested==[1,2]

def test_github_repository_request_uses_server_side_installation_token(monkeypatch):
    from app.services.github import GitHubClient
    client=GitHubClient.__new__(GitHubClient)
    monkeypatch.setattr(client,"installation_token",lambda installation_id:"test-installation-token")
    captured={}
    class Response:
        def raise_for_status(self):pass
        def json(self):return {"repositories":[]}
    def fake_get(url,**kwargs):
        captured.update(url=url,**kwargs)
        return Response()
    monkeypatch.setattr("app.services.github.httpx.get",fake_get)
    assert client.request("7766","/installation/repositories",{"per_page":100})=={"repositories":[]}
    assert captured["url"]=="https://api.github.com/installation/repositories"
    assert captured["headers"]["Authorization"]=="Bearer test-installation-token"

def test_github_webhook_signature_dedup_and_uninstall_revoke(client,monkeypatch):
    headers=auth(client);installation_row_id=add_installation();monkeypatch.setattr(settings,"github_webhook_secret","unit-test-webhook-secret")
    body=json.dumps({"action":"deleted","installation":{"id":7766}}).encode()
    signature="sha256="+hmac.new(b"unit-test-webhook-secret",body,hashlib.sha256).hexdigest()
    webhook_headers={"x-hub-signature-256":signature,"x-github-delivery":"delivery-uninstall-1","x-github-event":"installation"}
    first=client.post("/api/webhooks/github",content=body,headers=webhook_headers);assert first.status_code==200 and first.json()["duplicate"] is False
    duplicate=client.post("/api/webhooks/github",content=body,headers=webhook_headers);assert duplicate.status_code==200 and duplicate.json()["duplicate"] is True
    db=SessionLocal()
    try:assert db.get(GitHubInstallation,installation_row_id).status=="revoked"
    finally:db.close()
