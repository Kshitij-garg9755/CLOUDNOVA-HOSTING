import hashlib
import hmac
import json
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

def test_installation_repository_listing_and_branch_selection(client,monkeypatch):
    headers=auth(client);add_installation()
    monkeypatch.setattr(settings,"github_app_id","test-app-id");monkeypatch.setattr(settings,"github_private_key","test-key")
    def fake_request(self,installation_id,path,params=None):
        if path=="/installation/repositories":return {"repositories":[{"id":991,"full_name":"cloudnova-test/site","private":True,"default_branch":"trunk"}]}
        if path.endswith("/branches"):return [{"name":"trunk","protected":True},{"name":"preview","protected":False}]
        if path=="/repos/cloudnova-test/site":return {"default_branch":"trunk","private":True,"html_url":"https://github.com/cloudnova-test/site","description":"Site"}
        raise AssertionError(path)
    monkeypatch.setattr("app.api.deployments.GitHubClient.request",fake_request)
    repos=client.get("/api/github/repositories",headers=headers);assert repos.status_code==200
    repository_id=repos.json()["items"][0]["id"]
    details=client.get(f"/api/github/repositories/{repository_id}",headers=headers);assert details.json()["default_branch"]=="trunk"
    branches=client.get(f"/api/github/repositories/{repository_id}/branches",headers=headers)
    assert [b["name"] for b in branches.json()["items"]]==["trunk","preview"]

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
