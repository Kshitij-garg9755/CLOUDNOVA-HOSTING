import hashlib
from app.core.config import settings

class DemoDomainProvider:
    """Deterministic demo lookup. Never represents registrar availability."""
    def search(self, domain:str)->dict:
        name=domain.lower().strip().lstrip("@");available=int(hashlib.sha256(name.encode()).hexdigest(),16)%3!=0
        return {"domain":name,"available":available,"price":899 if name.endswith(".com") else 599,"mode":"DEMO","message":"Mock result only; verify with a registrar."}
class DemoHostingProvider:
    mode="DEMO"
    def provision(self,account:str,plan:str)->dict:return {"status":"demo_pending","provider_ref":None,"mode":self.mode}
    def suspend(self,ref:str)->dict:return {"status":"suspended","mode":self.mode}
    def activate(self,ref:str)->dict:return {"status":"active","mode":self.mode}
    def cancel(self,ref:str)->dict:return {"status":"cancelled","mode":self.mode}
    def status(self,ref:str)->dict:return {"status":"demo_pending","mode":self.mode,"resources":{}}
class PaymentService:
    def create_order(self,amount:int,receipt:str)->dict:
        if settings.razorpay_key_id and settings.razorpay_key_secret:
            import razorpay
            client=razorpay.Client(auth=(settings.razorpay_key_id,settings.razorpay_key_secret))
            return {**client.order.create({"amount":amount,"currency":"INR","receipt":receipt}),"mode":"razorpay_test"}
        if not settings.payment_demo_mode: raise ValueError("Razorpay credentials are not configured")
        return {"id":"demo_"+receipt,"amount":amount,"currency":"INR","status":"created","mode":"DEMO"}
