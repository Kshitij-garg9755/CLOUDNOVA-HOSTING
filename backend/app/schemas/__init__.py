from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Any
class RegisterIn(BaseModel): name:str=Field(min_length=2,max_length=120);email:EmailStr;password:str=Field(min_length=8,max_length=128)
class ProfileIn(BaseModel): name:str|None=Field(default=None,min_length=2,max_length=120);phone:str|None=Field(default=None,max_length=32)
class PlanIn(BaseModel): name:str=Field(min_length=2,max_length=100);description:str="";price_monthly:float=Field(gt=0);storage_gb:int=Field(gt=0);bandwidth_gb:int=Field(gt=0);features:list[str]=[]
class ContactIn(BaseModel): name:str=Field(min_length=2,max_length=120);email:EmailStr;subject:str=Field(min_length=3,max_length=200);message:str=Field(min_length=10,max_length=5000)
class TicketIn(BaseModel): subject:str=Field(min_length=3,max_length=200);message:str=Field(min_length=5,max_length=5000)
class DomainIn(BaseModel): domain:str=Field(min_length=3,max_length=253)
class OrderIn(BaseModel): plan_id:str
class VerifyIn(BaseModel): razorpay_order_id:str;razorpay_payment_id:str;razorpay_signature:str
