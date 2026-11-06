import hashlib,hmac,secrets
from datetime import datetime,timedelta,timezone
from fastapi import APIRouter,Depends,HTTPException,Request,Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.core.security import hash_password,verify_password,create_token,decode_token
from app.core.config import settings
from app.models import User,HostingPlan,Domain,Order,OrderItem,Payment,Subscription,SupportTicket,TicketMessage,ContactMessage,Invoice,ActivityLog,PasswordResetToken
from app.schemas import RegisterIn,PlanIn,ContactIn,TicketIn,DomainIn,OrderIn,ProfileIn,VerifyIn
from app.services.providers import DemoDomainProvider,DemoHostingProvider,PaymentService

router=APIRouter(prefix="/api")
oauth=OAuth2PasswordBearer(tokenUrl="/api/auth/login")
def current_user(token:str=Depends(oauth),db:Session=Depends(get_db)):
    uid=decode_token(token)
    user=db.get(User,uid) if uid else None
    if not user or not user.is_active:raise HTTPException(401,"Invalid or expired authentication")
    return user
def admin_user(user:User=Depends(current_user)):
    if user.role!="admin":raise HTTPException(403,"Administrator access required")
    return user
def page(q,limit:int,offset:int):return q.offset(offset).limit(limit).all()
def public_plan(p):return {"id":p.id,"name":p.name,"description":p.description,"price_monthly":p.price_monthly,"storage_gb":p.storage_gb,"bandwidth_gb":p.bandwidth_gb,"features":p.features,"active":p.active}

@router.post("/auth/register",status_code=201)
def register(data:RegisterIn,db:Session=Depends(get_db)):
    if db.query(User).filter(func.lower(User.email)==data.email.lower()).first():raise HTTPException(409,"An account with this email already exists")
    u=User(name=data.name,email=data.email.lower(),password_hash=hash_password(data.password));db.add(u);db.commit();db.refresh(u);db.add(ActivityLog(user_id=u.id,action="account.registered",description="Account created"));db.commit();return {"id":u.id,"name":u.name,"email":u.email,"role":u.role}
@router.post("/auth/login")
async def login(request:Request,db:Session=Depends(get_db)):
    form=await request.form();email=str(form.get("username") or form.get("email") or "").lower();password=str(form.get("password") or "")
    u=db.query(User).filter(func.lower(User.email)==email).first()
    if not u or not verify_password(password,u.password_hash):raise HTTPException(401,"Email or password is incorrect")
    return {"access_token":create_token(u.id),"token_type":"bearer","expires_in":settings.access_token_minutes*60}
@router.post("/auth/logout")
def logout():return {"message":"Signed out. Remove the bearer token from the client."}
@router.get("/auth/me")
def me(u:User=Depends(current_user)):return {"id":u.id,"name":u.name,"email":u.email,"role":u.role,"phone":u.phone}
@router.patch("/auth/me")
def profile(data:ProfileIn,u:User=Depends(current_user),db:Session=Depends(get_db)):
    for k,v in data.model_dump(exclude_unset=True).items():setattr(u,k,v)
    db.commit();db.refresh(u);return {"id":u.id,"name":u.name,"email":u.email,"phone":u.phone,"role":u.role}
@router.post("/auth/forgot-password")
def forgot(data:dict,db:Session=Depends(get_db)):
    email=str(data.get("email","")).lower();u=db.query(User).filter(func.lower(User.email)==email).first();result={"message":"If the account exists, reset instructions will be sent."}
    if u:
        raw=secrets.token_urlsafe(32);db.add(PasswordResetToken(user_id=u.id,token_hash=hashlib.sha256(raw.encode()).hexdigest(),expires_at=datetime.now(timezone.utc)+timedelta(minutes=30)));db.commit()
        if settings.payment_demo_mode:result["demo_reset_token"]=raw
    return result
@router.post("/auth/reset-password")
def reset(data:dict,db:Session=Depends(get_db)):
    raw=data.get("token","");row=db.query(PasswordResetToken).filter_by(token_hash=hashlib.sha256(raw.encode()).hexdigest(),used=False).first()
    if not row or row.expires_at.replace(tzinfo=timezone.utc)<datetime.now(timezone.utc):raise HTTPException(400,"Reset token is invalid or expired")
    password=str(data.get("password", ""))
    if len(password)<8:raise HTTPException(422,"Password must be at least 8 characters")
    u=db.get(User,row.user_id);u.password_hash=hash_password(password);row.used=True;db.commit();return {"message":"Password updated"}

@router.get("/plans")
def plans(db:Session=Depends(get_db),search:str|None=None,limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
    q=db.query(HostingPlan).filter(HostingPlan.active.is_(True))
    if search:q=q.filter(HostingPlan.name.ilike(f"%{search}%"))
    total=q.count();return {"items":[public_plan(p) for p in page(q.order_by(HostingPlan.price_monthly),limit,offset)],"total":total,"limit":limit,"offset":offset}
@router.get("/plans/{plan_id}")
def get_plan(plan_id:str,db:Session=Depends(get_db)):
    p=db.get(HostingPlan,plan_id)
    if not p or not p.active:raise HTTPException(404,"Plan not found")
    return public_plan(p)
@router.post("/admin/plans",status_code=201)
def create_plan(data:PlanIn,db:Session=Depends(get_db),_:User=Depends(admin_user)):
    p=HostingPlan(**data.model_dump());db.add(p)
    try:db.commit()
    except Exception:db.rollback();raise HTTPException(409,"Plan name already exists")
    db.refresh(p);return public_plan(p)
@router.put("/admin/plans/{plan_id}")
def update_plan(plan_id:str,data:PlanIn,db:Session=Depends(get_db),_:User=Depends(admin_user)):
    p=db.get(HostingPlan,plan_id)
    if not p:raise HTTPException(404,"Plan not found")
    for k,v in data.model_dump().items():setattr(p,k,v)
    db.commit();db.refresh(p);return public_plan(p)
@router.delete("/admin/plans/{plan_id}")
def delete_plan(plan_id:str,db:Session=Depends(get_db),_:User=Depends(admin_user)):
    p=db.get(HostingPlan,plan_id)
    if not p:raise HTTPException(404,"Plan not found")
    p.active=False;db.commit();return {"message":"Plan archived"}

@router.post("/domains/search")
def domain_search(data:DomainIn):
    domain=data.domain.strip().lower()
    if " " in domain or "." not in domain:raise HTTPException(422,"Enter a full domain name, such as example.com")
    return DemoDomainProvider().search(domain)
@router.get("/domains")
def domains(db:Session=Depends(get_db),u:User=Depends(current_user),limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
    q=db.query(Domain).filter(Domain.user_id==u.id);return {"items":[domain_dict(x) for x in page(q,limit,offset)],"total":q.count()}
def domain_dict(x):return {"id":x.id,"domain":x.name,"status":x.status,"registered_at":x.registered_at,"expires_at":x.expires_at,"demo":x.demo}
@router.post("/domains/register",status_code=201)
def domain_register(data:DomainIn,db:Session=Depends(get_db),u:User=Depends(current_user)):
    result=DemoDomainProvider().search(data.domain)
    if not result["available"]:raise HTTPException(409,"Demo lookup reports this name unavailable")
    d=Domain(user_id=u.id,name=result["domain"],status="demo_pending",demo=True);db.add(d);db.commit();db.refresh(d);return domain_dict(d)

@router.post("/orders",status_code=201)
def create_order(data:OrderIn,db:Session=Depends(get_db),u:User=Depends(current_user)):
    p=db.get(HostingPlan,data.plan_id)
    if not p or not p.active:raise HTTPException(404,"Plan not found")
    o=Order(user_id=u.id,plan_id=p.id,status="pending",amount=p.price_monthly);db.add(o);db.flush();db.add(OrderItem(order_id=o.id,description=p.name,quantity=1,unit_price=p.price_monthly));db.add(ActivityLog(user_id=u.id,action="order.created",description=f"Order for {p.name}"));db.commit();db.refresh(o);return order_dict(o,p.name)
def order_dict(o,plan_name=None):return {"id":o.id,"user_id":o.user_id,"plan_id":o.plan_id,"plan_name":plan_name,"status":o.status,"amount":o.amount,"currency":o.currency,"created_at":o.created_at}
@router.get("/orders")
def orders(db:Session=Depends(get_db),u:User=Depends(current_user),limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
    q=db.query(Order).filter(Order.user_id==u.id);return {"items":[order_dict(o,db.get(HostingPlan,o.plan_id).name if o.plan_id and db.get(HostingPlan,o.plan_id) else None) for o in page(q.order_by(Order.created_at.desc()),limit,offset)],"total":q.count()}
@router.get("/orders/{order_id}")
def get_order(order_id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    o=db.get(Order,order_id)
    if not o or (o.user_id!=u.id and u.role!="admin"):raise HTTPException(404,"Order not found")
    p=db.get(HostingPlan,o.plan_id) if o.plan_id else None;return order_dict(o,p.name if p else None)

@router.post("/payments/create")
def create_payment(data:dict,db:Session=Depends(get_db),u:User=Depends(current_user)):
    o=db.get(Order,data.get("order_id"))
    if not o or o.user_id!=u.id:raise HTTPException(404,"Order not found")
    if o.status!="pending":raise HTTPException(409,"Order is not payable")
    try:result=PaymentService().create_order(int(o.amount*100),o.id)
    except ValueError as e:raise HTTPException(503,str(e))
    provider_id=result["id"];existing=db.query(Payment).filter_by(provider_id=provider_id).first()
    if not existing:db.add(Payment(order_id=o.id,provider_id=provider_id,status="created",amount=o.amount));db.commit()
    return {"payment_order":result,"key_id":settings.razorpay_key_id or None,"mode":result.get("mode","DEMO")}
@router.post("/payments/verify")
def verify_payment(data:VerifyIn,db:Session=Depends(get_db),u:User=Depends(current_user)):
    pay=db.query(Payment).filter_by(provider_id=data.razorpay_order_id).first()
    if not pay:raise HTTPException(404,"Payment order not found")
    order=db.get(Order,pay.order_id)
    if order.user_id!=u.id:raise HTTPException(404,"Payment order not found")
    if pay.status=="paid":return {"status":"paid","message":"Already processed"}
    if pay.status == "paid":return {"status":"paid","message":"Already processed"}
    if data.razorpay_order_id.startswith("demo_"):
        if not settings.payment_demo_mode:raise HTTPException(400,"Demo payment mode disabled")
        valid=hmac.compare_digest(data.razorpay_signature,"demo_signature")
    else:
        expected=hmac.new(settings.razorpay_key_secret.encode(),f"{data.razorpay_order_id}|{data.razorpay_payment_id}".encode(),hashlib.sha256).hexdigest()
        valid=bool(settings.razorpay_key_secret) and hmac.compare_digest(expected,data.razorpay_signature)
    if not valid:raise HTTPException(400,"Payment signature verification failed")
    pay.status="paid";order.status="paid"
    if not db.query(Invoice).filter_by(order_id=order.id).first():db.add(Invoice(user_id=u.id,order_id=order.id,number="CN-"+order.id[:10].upper(),amount=order.amount))
    if not db.query(Subscription).filter_by(user_id=u.id,plan_id=order.plan_id).filter(Subscription.created_at>=order.created_at).first():db.add(Subscription(user_id=u.id,plan_id=order.plan_id,status="demo_pending",demo=True))
    DemoHostingProvider().provision(u.id,order.plan_id or "");db.commit();return {"status":"paid","message":"Signature verified; hosting remains DEMO until a provider is configured"}
@router.post("/payments/webhook")
async def payment_webhook(request:Request,db:Session=Depends(get_db)):
    body=await request.body();signature=request.headers.get("x-razorpay-signature","")
    if not settings.razorpay_webhook_secret:raise HTTPException(503,"Webhook secret is not configured")
    expected=hmac.new(settings.razorpay_webhook_secret.encode(),body,hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature,expected):raise HTTPException(400,"Invalid webhook signature")
    import json
    event=json.loads(body);entity=event.get("payload",{}).get("payment",{}).get("entity",{});order_id=entity.get("order_id");payment_id=entity.get("id")
    pay=db.query(Payment).filter_by(provider_id=order_id).first()
    if pay and event.get("event")=="payment.captured" and pay.status!="paid":
        order=db.get(Order,pay.order_id);pay.status="paid";order.status="paid"
        if not db.query(Invoice).filter_by(order_id=order.id).first():db.add(Invoice(user_id=order.user_id,order_id=order.id,number="CN-"+order.id[:10].upper(),amount=order.amount))
        if not db.query(Subscription).filter_by(user_id=order.user_id,plan_id=order.plan_id).filter(Subscription.created_at>=order.created_at).first():db.add(Subscription(user_id=order.user_id,plan_id=order.plan_id,status="demo_pending",demo=True))
        db.commit()
    elif pay and event.get("event")=="payment.failed":pay.status="failed";db.commit()
    return {"received":True}

@router.get("/dashboard/overview")
def dashboard(db:Session=Depends(get_db),u:User=Depends(current_user)):
    services=db.query(Subscription).filter_by(user_id=u.id).count();active=db.query(Subscription).filter_by(user_id=u.id,status="active").count();domains_n=db.query(Domain).filter_by(user_id=u.id).count();pending=db.query(Order).filter_by(user_id=u.id,status="pending").count();activity=db.query(ActivityLog).filter_by(user_id=u.id).order_by(ActivityLog.created_at.desc()).limit(8).all()
    return {"counts":{"services":services,"active":active,"domains":domains_n,"pending_payments":pending},"recent_activity":[{"action":x.action,"description":x.description,"created_at":x.created_at} for x in activity]}
@router.get("/dashboard/hosting")
def customer_hosting(db:Session=Depends(get_db),u:User=Depends(current_user)):
    rows=db.query(Subscription).filter_by(user_id=u.id).all();return {"items":[{"id":s.id,"status":s.status,"demo":s.demo,"plan_name":(db.get(HostingPlan,s.plan_id).name if s.plan_id and db.get(HostingPlan,s.plan_id) else "Hosting"),"created_at":s.created_at} for s in rows]}
@router.get("/dashboard/domains")
def customer_domains(db:Session=Depends(get_db),u:User=Depends(current_user)):return domains(db,u,50,0)
@router.get("/dashboard/invoices")
def invoices(db:Session=Depends(get_db),u:User=Depends(current_user)):
    return {"items":[{"id":i.id,"number":i.number,"amount":i.amount,"created_at":i.created_at,"download_url":f"/api/dashboard/invoices/{i.id}/download"} for i in db.query(Invoice).filter_by(user_id=u.id).all()]}
@router.get("/dashboard/invoices/{invoice_id}/download")
def invoice_download(invoice_id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    i=db.get(Invoice,invoice_id)
    if not i or i.user_id!=u.id:raise HTTPException(404,"Invoice not found")
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(f"CloudNova Hosting\nInvoice {i.number}\nAmount: INR {i.amount:.2f}\nIssued: {i.created_at}\nDEMO invoice",media_type="text/plain",headers={"Content-Disposition":f'attachment; filename="{i.number}.txt"'})

@router.post("/support/tickets",status_code=201)
def ticket_create(data:TicketIn,db:Session=Depends(get_db),u:User=Depends(current_user)):
    t=SupportTicket(user_id=u.id,subject=data.subject);db.add(t);db.flush();db.add(TicketMessage(ticket_id=t.id,sender_id=u.id,message=data.message));db.commit();db.refresh(t);return {"id":t.id,"subject":t.subject,"status":t.status,"created_at":t.created_at}
@router.get("/support/tickets")
def ticket_list(db:Session=Depends(get_db),u:User=Depends(current_user),limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
    q=db.query(SupportTicket).filter(SupportTicket.user_id==u.id);return {"items":[ticket_dict(x) for x in page(q.order_by(SupportTicket.created_at.desc()),limit,offset)],"total":q.count()}
def ticket_dict(t):return {"id":t.id,"subject":t.subject,"status":t.status,"created_at":t.created_at}
@router.get("/support/tickets/{ticket_id}")
def ticket_get(ticket_id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    t=db.get(SupportTicket,ticket_id)
    if not t or (t.user_id!=u.id and u.role!="admin"):raise HTTPException(404,"Ticket not found")
    msgs=db.query(TicketMessage).filter_by(ticket_id=t.id).order_by(TicketMessage.created_at).all();return {**ticket_dict(t),"messages":[{"sender_id":m.sender_id,"message":m.message,"created_at":m.created_at} for m in msgs]}
@router.post("/support/tickets/{ticket_id}/messages",status_code=201)
def ticket_message(ticket_id:str,data:dict,db:Session=Depends(get_db),u:User=Depends(current_user)):
    t=db.get(SupportTicket,ticket_id)
    if not t or (t.user_id!=u.id and u.role!="admin"):raise HTTPException(404,"Ticket not found")
    message=str(data.get("message", ""))
    if len(message)<2 or len(message)>5000:raise HTTPException(422,"Message must contain 2 to 5000 characters")
    m=TicketMessage(ticket_id=t.id,sender_id=u.id,message=message);db.add(m);db.commit();return {"id":m.id,"message":m.message,"created_at":m.created_at}

@router.post("/contact",status_code=201)
def contact(data:ContactIn,db:Session=Depends(get_db)):
    m=ContactMessage(**data.model_dump());db.add(m);db.commit();return {"message":"Thanks for contacting CloudNova"}
@router.get("/admin/contact-messages")
def contact_admin(db:Session=Depends(get_db),_:User=Depends(admin_user),search:str|None=None,limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
    q=db.query(ContactMessage)
    if search:q=q.filter(ContactMessage.email.ilike(f"%{search}%")|ContactMessage.subject.ilike(f"%{search}%"))
    return {"items":[contact_dict(x) for x in page(q.order_by(ContactMessage.created_at.desc()),limit,offset)],"total":q.count()}
def contact_dict(x):return {"id":x.id,"name":x.name,"email":x.email,"subject":x.subject,"message":x.message,"created_at":x.created_at}

@router.get("/admin/dashboard")
def admin_dashboard(db:Session=Depends(get_db),_:User=Depends(admin_user)):
    return {"stats":{"users":db.query(User).count(),"revenue":db.query(func.sum(Payment.amount)).filter(Payment.status=="paid").scalar() or 0,"orders":db.query(Order).count(),"subscriptions":db.query(Subscription).filter(Subscription.status=="active").count()},"recent_transactions":[]}
def admin_rows(q,limit,offset):return q.offset(offset).limit(limit).all()
@router.get("/admin/users")
def admin_users(db:Session=Depends(get_db),_:User=Depends(admin_user),search:str|None=None,limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
    q=db.query(User)
    if search:q=q.filter(User.email.ilike(f"%{search}%")|User.name.ilike(f"%{search}%"))
    return {"items":[{"id":x.id,"name":x.name,"email":x.email,"role":x.role,"is_active":x.is_active,"created_at":x.created_at} for x in admin_rows(q,limit,offset)],"total":q.count()}
@router.patch("/admin/users/{user_id}/status")
def user_status(user_id:str,data:dict,db:Session=Depends(get_db),_:User=Depends(admin_user)):
    u=db.get(User,user_id)
    if not u:raise HTTPException(404,"User not found")
    u.is_active=bool(data.get("is_active"));db.commit();return {"id":u.id,"is_active":u.is_active}
@router.get("/admin/orders")
def admin_orders(db:Session=Depends(get_db),_:User=Depends(admin_user),status:str|None=None,limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
    q=db.query(Order)
    if status:q=q.filter(Order.status==status)
    rows=admin_rows(q.order_by(Order.created_at.desc()),limit,offset);return {"items":[order_dict(o,db.get(HostingPlan,o.plan_id).name if o.plan_id and db.get(HostingPlan,o.plan_id) else None) for o in rows],"total":q.count()}
@router.patch("/admin/orders/{order_id}")
def admin_order_status(order_id:str,data:dict,db:Session=Depends(get_db),_:User=Depends(admin_user)):
    o=db.get(Order,order_id);status=data.get("status")
    if not o:raise HTTPException(404,"Order not found")
    if status not in {"pending","paid","failed","cancelled","refunded"}:raise HTTPException(422,"Invalid order status")
    o.status=status;db.commit();return order_dict(o)
@router.get("/admin/payments")
def admin_payments(db:Session=Depends(get_db),_:User=Depends(admin_user),limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
    q=db.query(Payment);return {"items":[{"id":p.id,"order_id":p.order_id,"provider_id":p.provider_id,"status":p.status,"amount":p.amount,"currency":p.currency,"created_at":p.created_at} for p in admin_rows(q.order_by(Payment.created_at.desc()),limit,offset)],"total":q.count()}
@router.get("/admin/subscriptions")
def admin_subscriptions(db:Session=Depends(get_db),_:User=Depends(admin_user),limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
    q=db.query(Subscription);return {"items":[{"id":x.id,"user_id":x.user_id,"plan_id":x.plan_id,"status":x.status,"demo":x.demo,"created_at":x.created_at} for x in admin_rows(q,limit,offset)],"total":q.count()}
@router.patch("/admin/subscriptions/{subscription_id}")
def update_subscription(subscription_id:str,data:dict,db:Session=Depends(get_db),_:User=Depends(admin_user)):
    s=db.get(Subscription,subscription_id)
    if not s:raise HTTPException(404,"Subscription not found")
    status=data.get("status")
    if status not in {"pending","active","suspended","cancelled","demo_pending"}:raise HTTPException(422,"Invalid status")
    s.status=status;db.commit();return {"id":s.id,"status":s.status}
@router.get("/admin/tickets")
def admin_tickets(db:Session=Depends(get_db),_:User=Depends(admin_user),status:str|None=None,limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
    q=db.query(SupportTicket)
    if status:q=q.filter(SupportTicket.status==status)
    return {"items":[{**ticket_dict(t),"user_id":t.user_id} for t in admin_rows(q.order_by(SupportTicket.created_at.desc()),limit,offset)],"total":q.count()}
@router.patch("/admin/tickets/{ticket_id}")
def admin_ticket_status(ticket_id:str,data:dict,db:Session=Depends(get_db),_:User=Depends(admin_user)):
    t=db.get(SupportTicket,ticket_id)
    if not t:raise HTTPException(404,"Ticket not found")
    if data.get("status") not in {"open","in_progress","resolved","closed"}:raise HTTPException(422,"Invalid status")
    t.status=data["status"];db.commit();return ticket_dict(t)
