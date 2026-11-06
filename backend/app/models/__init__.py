import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Float, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

def uid(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc)
class User(Base):
    __tablename__="users"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);name:Mapped[str]=mapped_column(String(120));email:Mapped[str]=mapped_column(String(255),unique=True,index=True);password_hash:Mapped[str]=mapped_column(String(255));role:Mapped[str]=mapped_column(String(20),default="customer");is_active:Mapped[bool]=mapped_column(Boolean,default=True);phone:Mapped[str|None]=mapped_column(String(32),nullable=True);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class HostingPlan(Base):
    __tablename__="hosting_plans"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);name:Mapped[str]=mapped_column(String(100),unique=True);description:Mapped[str]=mapped_column(Text,default="");price_monthly:Mapped[float]=mapped_column(Float);storage_gb:Mapped[int]=mapped_column(Integer,default=20);bandwidth_gb:Mapped[int]=mapped_column(Integer,default=100);features:Mapped[list]=mapped_column(JSON,default=list);active:Mapped[bool]=mapped_column(Boolean,default=True);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Domain(Base):
    __tablename__="domains"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);name:Mapped[str]=mapped_column(String(253),index=True);status:Mapped[str]=mapped_column(String(24),default="pending");registered_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True);expires_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True);demo:Mapped[bool]=mapped_column(Boolean,default=True)
class Order(Base):
    __tablename__="orders"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);plan_id:Mapped[str|None]=mapped_column(ForeignKey("hosting_plans.id",ondelete="SET NULL"),nullable=True);status:Mapped[str]=mapped_column(String(24),default="pending");amount:Mapped[float]=mapped_column(Float);currency:Mapped[str]=mapped_column(String(3),default="INR");created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class OrderItem(Base):
    __tablename__="order_items"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);order_id:Mapped[str]=mapped_column(ForeignKey("orders.id",ondelete="CASCADE"),index=True);description:Mapped[str]=mapped_column(String(255));quantity:Mapped[int]=mapped_column(Integer,default=1);unit_price:Mapped[float]=mapped_column(Float)
class Payment(Base):
    __tablename__="payments"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);order_id:Mapped[str]=mapped_column(ForeignKey("orders.id",ondelete="CASCADE"),index=True);provider_id:Mapped[str|None]=mapped_column(String(180),unique=True,nullable=True);status:Mapped[str]=mapped_column(String(24),default="created");amount:Mapped[float]=mapped_column(Float);currency:Mapped[str]=mapped_column(String(3),default="INR");created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Subscription(Base):
    __tablename__="subscriptions"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);plan_id:Mapped[str|None]=mapped_column(ForeignKey("hosting_plans.id",ondelete="SET NULL"),nullable=True);status:Mapped[str]=mapped_column(String(24),default="pending");provider_ref:Mapped[str|None]=mapped_column(String(180),nullable=True);demo:Mapped[bool]=mapped_column(Boolean,default=True);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class SupportTicket(Base):
    __tablename__="support_tickets"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);subject:Mapped[str]=mapped_column(String(200));status:Mapped[str]=mapped_column(String(24),default="open");created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class TicketMessage(Base):
    __tablename__="ticket_messages"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);ticket_id:Mapped[str]=mapped_column(ForeignKey("support_tickets.id",ondelete="CASCADE"),index=True);sender_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"));message:Mapped[str]=mapped_column(Text);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class ContactMessage(Base):
    __tablename__="contact_messages"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);name:Mapped[str]=mapped_column(String(120));email:Mapped[str]=mapped_column(String(255),index=True);subject:Mapped[str]=mapped_column(String(200));message:Mapped[str]=mapped_column(Text);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Invoice(Base):
    __tablename__="invoices"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);order_id:Mapped[str]=mapped_column(ForeignKey("orders.id",ondelete="CASCADE"),unique=True);number:Mapped[str]=mapped_column(String(40),unique=True);amount:Mapped[float]=mapped_column(Float);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class ActivityLog(Base):
    __tablename__="activity_logs"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);user_id:Mapped[str|None]=mapped_column(ForeignKey("users.id",ondelete="SET NULL"),nullable=True,index=True);action:Mapped[str]=mapped_column(String(120));description:Mapped[str]=mapped_column(Text,default="");created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class PasswordResetToken(Base):
    __tablename__="password_reset_tokens"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);token_hash:Mapped[str]=mapped_column(String(255),unique=True);expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True));used:Mapped[bool]=mapped_column(Boolean,default=False)
class GitHubInstallation(Base):
    __tablename__="github_installations"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);installation_id:Mapped[str]=mapped_column(String(40),unique=True,index=True);account_login:Mapped[str]=mapped_column(String(120));account_type:Mapped[str]=mapped_column(String(30),default="Organization");status:Mapped[str]=mapped_column(String(24),default="active");created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class GitHubRepository(Base):
    __tablename__="github_repositories"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);installation_id:Mapped[str]=mapped_column(ForeignKey("github_installations.id",ondelete="CASCADE"),index=True);github_repo_id:Mapped[str]=mapped_column(String(40),index=True);full_name:Mapped[str]=mapped_column(String(255));owner:Mapped[str|None]=mapped_column(String(120),nullable=True);description:Mapped[str|None]=mapped_column(Text,nullable=True);private:Mapped[bool]=mapped_column(Boolean,default=True);default_branch:Mapped[str]=mapped_column(String(120),default="main");accessible:Mapped[bool]=mapped_column(Boolean,default=True);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Project(Base):
    __tablename__="projects"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);repository_id:Mapped[str]=mapped_column(ForeignKey("github_repositories.id",ondelete="CASCADE"),index=True);name:Mapped[str]=mapped_column(String(100));slug:Mapped[str]=mapped_column(String(100),unique=True,index=True);branch:Mapped[str]=mapped_column(String(120));framework:Mapped[str]=mapped_column(String(60),default="unknown");root_directory:Mapped[str]=mapped_column(String(500),default=".");frontend_directory:Mapped[str|None]=mapped_column(String(500),nullable=True);backend_directory:Mapped[str|None]=mapped_column(String(500),nullable=True);install_command:Mapped[str|None]=mapped_column(String(500),nullable=True);build_command:Mapped[str|None]=mapped_column(String(500),nullable=True);start_command:Mapped[str|None]=mapped_column(String(500),nullable=True);output_directory:Mapped[str|None]=mapped_column(String(300),nullable=True);runtime_version:Mapped[str|None]=mapped_column(String(40),nullable=True);app_port:Mapped[int|None]=mapped_column(Integer,nullable=True);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now);updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)
class Deployment(Base):
    __tablename__="deployments"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);project_id:Mapped[str]=mapped_column(ForeignKey("projects.id",ondelete="CASCADE"),index=True);user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);status:Mapped[str]=mapped_column(String(24),default="QUEUED",index=True);commit_sha:Mapped[str|None]=mapped_column(String(64),nullable=True);commit_message:Mapped[str|None]=mapped_column(Text,nullable=True);live_url:Mapped[str|None]=mapped_column(String(500),nullable=True);error_message:Mapped[str|None]=mapped_column(Text,nullable=True);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now);started_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True);finished_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
class DeploymentLog(Base):
    __tablename__="deployment_logs"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);deployment_id:Mapped[str]=mapped_column(ForeignKey("deployments.id",ondelete="CASCADE"),index=True);sequence:Mapped[int]=mapped_column(Integer);stream:Mapped[str]=mapped_column(String(12),default="stdout");message:Mapped[str]=mapped_column(Text);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class WebhookEvent(Base):
    __tablename__="webhook_events"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);delivery_id:Mapped[str]=mapped_column(String(100),unique=True,index=True);event_type:Mapped[str]=mapped_column(String(80));installation_id:Mapped[str|None]=mapped_column(String(40),nullable=True);processed:Mapped[bool]=mapped_column(Boolean,default=False);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class EnvironmentVariable(Base):
    __tablename__="environment_variables"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);project_id:Mapped[str]=mapped_column(ForeignKey("projects.id",ondelete="CASCADE"),index=True);name:Mapped[str]=mapped_column(String(120));encrypted_value:Mapped[str]=mapped_column(Text);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now);__table_args__=(Index("uq_env_project_name","project_id","name",unique=True),)
class CustomDomain(Base):
    __tablename__="custom_domains"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);project_id:Mapped[str]=mapped_column(ForeignKey("projects.id",ondelete="CASCADE"),index=True);hostname:Mapped[str]=mapped_column(String(253),unique=True,index=True);verification_token:Mapped[str]=mapped_column(String(100));verified:Mapped[bool]=mapped_column(Boolean,default=False);status:Mapped[str]=mapped_column(String(24),default="pending_dns");created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class ResourceUsage(Base):
    __tablename__="resource_usage"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);project_id:Mapped[str|None]=mapped_column(ForeignKey("projects.id",ondelete="CASCADE"),nullable=True,index=True);metric:Mapped[str]=mapped_column(String(50));value:Mapped[float]=mapped_column(Float);unit:Mapped[str]=mapped_column(String(20));created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class BuildWorker(Base):
    __tablename__="build_workers"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);worker_name:Mapped[str]=mapped_column(String(120),unique=True);status:Mapped[str]=mapped_column(String(24),default="unknown");isolation_runtime:Mapped[str|None]=mapped_column(String(80),nullable=True);last_heartbeat:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class DeploymentArtifact(Base):
    __tablename__="deployment_artifacts"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);deployment_id:Mapped[str]=mapped_column(ForeignKey("deployments.id",ondelete="CASCADE"),index=True);object_key:Mapped[str]=mapped_column(String(500));checksum:Mapped[str]=mapped_column(String(128));size_bytes:Mapped[int]=mapped_column(Integer);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class ProjectBranch(Base):
    __tablename__="project_branches"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);project_id:Mapped[str]=mapped_column(ForeignKey("projects.id",ondelete="CASCADE"),index=True);name:Mapped[str]=mapped_column(String(120));is_deploy_branch:Mapped[bool]=mapped_column(Boolean,default=False);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class RuntimeService(Base):
    __tablename__="runtime_services"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);project_id:Mapped[str]=mapped_column(ForeignKey("projects.id",ondelete="CASCADE"),unique=True,index=True);status:Mapped[str]=mapped_column(String(24),default="not_configured");provider_ref:Mapped[str|None]=mapped_column(String(180),nullable=True);app_port:Mapped[int|None]=mapped_column(Integer,nullable=True);last_health_check:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class SSLCertificate(Base):
    __tablename__="ssl_certificates"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);domain_id:Mapped[str]=mapped_column(ForeignKey("custom_domains.id",ondelete="CASCADE"),unique=True,index=True);status:Mapped[str]=mapped_column(String(24),default="not_issued");issuer:Mapped[str|None]=mapped_column(String(80),nullable=True);expires_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True);last_error:Mapped[str|None]=mapped_column(Text,nullable=True);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class AuditLog(Base):
    __tablename__="audit_logs"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);user_id:Mapped[str|None]=mapped_column(ForeignKey("users.id",ondelete="SET NULL"),nullable=True,index=True);action:Mapped[str]=mapped_column(String(120),index=True);resource_type:Mapped[str]=mapped_column(String(80));resource_id:Mapped[str|None]=mapped_column(String(36),nullable=True);details:Mapped[dict]=mapped_column(JSON,default=dict);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
Index("ix_orders_user_created",Order.user_id,Order.created_at)
