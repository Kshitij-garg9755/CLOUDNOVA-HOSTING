def register(client,email="one@example.com",password="secret-pass-123"):
    return client.post('/api/auth/register',json={"name":"Test User","email":email,"password":password})
def token(client,email="one@example.com",password="secret-pass-123"):
    return client.post('/api/auth/login',data={"username":email,"password":password}).json()['access_token']
def test_register_login_me(client):
    assert register(client).status_code==201
    response=client.get('/api/auth/me',headers={"Authorization":"Bearer "+token(client)})
    assert response.status_code==200 and response.json()['email']=='one@example.com'
def test_public_register_cannot_be_admin(client):
    register(client);headers={"Authorization":"Bearer "+token(client)}
    assert client.post('/api/admin/plans',json={"name":"New","price_monthly":10,"storage_gb":1,"bandwidth_gb":1},headers=headers).status_code==403
def test_plan_catalog_seeded(client):
    response=client.get('/api/plans');assert response.status_code==200 and len(response.json()['items'])==4
def test_orders_are_customer_scoped(client):
    register(client);t1=token(client);plans=client.get('/api/plans').json()['items'];order=client.post('/api/orders',json={"plan_id":plans[0]['id']},headers={"Authorization":"Bearer "+t1});assert order.status_code==201
    register(client,"two@example.com");t2=token(client,"two@example.com");hidden=client.get('/api/orders/'+order.json()['id'],headers={"Authorization":"Bearer "+t2});assert hidden.status_code==404
def test_domain_results_marked_demo(client):
    result=client.post('/api/domains/search',json={"domain":"example.com"}).json();assert result['mode']=='DEMO'
def test_database_health_endpoint(client):
    response=client.get('/health');assert response.status_code==200 and response.json()['database']=='ok'
def test_github_disconnect_revokes_access_without_deleting_projects(client):
    from app.core.database import SessionLocal
    from app.models import User,GitHubInstallation,GitHubRepository,Project
    register(client);headers={"Authorization":"Bearer "+token(client)};db=SessionLocal()
    try:
        user=db.query(User).filter_by(email="one@example.com").one()
        installation=GitHubInstallation(user_id=user.id,installation_id="12345",account_login="example",account_type="Organization");db.add(installation);db.flush()
        repository=GitHubRepository(installation_id=installation.id,github_repo_id="789",full_name="example/site",private=True,default_branch="main");db.add(repository);db.flush()
        project=Project(user_id=user.id,repository_id=repository.id,name="Site",slug="site-test",branch="main");db.add(project);db.commit();project_id=project.id;installation_id=installation.id;repository_id=repository.id
    finally:db.close()
    response=client.post('/api/github/disconnect',headers=headers);assert response.status_code==200
    db=SessionLocal()
    try:
        assert db.get(Project,project_id) is not None
        assert db.get(GitHubInstallation,installation_id).status=="revoked"
        assert db.get(GitHubRepository,repository_id).accessible is False
    finally:db.close()
def test_payment_demo_requires_valid_demo_signature(client):
    register(client);headers={"Authorization":"Bearer "+token(client)};p=client.get('/api/plans').json()['items'][0];o=client.post('/api/orders',json={"plan_id":p['id']},headers=headers).json();po=client.post('/api/payments/create',json={"order_id":o['id']},headers=headers).json()['payment_order']
    bad=client.post('/api/payments/verify',json={"razorpay_order_id":po['id'],"razorpay_payment_id":"demo_pay","razorpay_signature":"wrong"},headers=headers);assert bad.status_code==400
