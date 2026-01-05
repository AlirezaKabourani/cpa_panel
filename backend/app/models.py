from sqlalchemy import Column, String, Integer, Text
from .db import Base

class Customer(Base):
    __tablename__ = "customers"
    id = Column(String, primary_key=True, index=True)
    code = Column(String, unique=True, index=True)   # slug
    name = Column(String, unique=True, index=True)
    service_id = Column(String, nullable=False)
    created_at = Column(String, nullable=False)

class CustomerMessage(Base):
    __tablename__ = "customer_messages"
    id = Column(String, primary_key=True, index=True)
    customer_id = Column(String, index=True, nullable=False)
    title = Column(String, nullable=True)
    text_template = Column(Text, nullable=False)
    created_at = Column(String, nullable=False)
    is_active = Column(Integer, nullable=False, default=1)

class CustomerMedia(Base):
    __tablename__ = "customer_media"
    id = Column(String, primary_key=True, index=True)
    customer_id = Column(String, index=True, nullable=False)
    file_id = Column(String, nullable=False)
    file_name = Column(String, nullable=True)
    file_type = Column(String, nullable=True)  # Image/Video
    created_at = Column(String, nullable=False)

# Stubs for later steps (keep now so DB schema is ready)
class AudienceSnapshot(Base):
    __tablename__ = "audience_snapshots"
    id = Column(String, primary_key=True, index=True)
    original_filename = Column(String, nullable=False)
    stored_path = Column(String, nullable=False)
    row_count = Column(Integer, nullable=False)
    hash = Column(String, nullable=False)
    created_at = Column(String, nullable=False)

class Campaign(Base):
    __tablename__ = "campaigns"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=True, index=True)
    customer_id = Column(String, index=True, nullable=False)
    audience_snapshot_id = Column(String, index=True, nullable=True)
    selected_file_id = Column(String, nullable=True)
    message_text = Column(Text, nullable=False)
    test_number = Column(String, nullable=True)
    status = Column(String, nullable=False)
    created_at = Column(String, nullable=False)

class Schedule(Base):
    __tablename__ = "schedules"
    id = Column(String, primary_key=True, index=True)
    campaign_id = Column(String, index=True, nullable=False)
    run_at = Column(String, nullable=False)  # ISO string
    timezone = Column(String, nullable=False)
    is_enabled = Column(Integer, nullable=False, default=1)

class Run(Base):
    __tablename__ = "runs"
    id = Column(String, primary_key=True, index=True)
    campaign_id = Column(String, index=True, nullable=False)
    status = Column(String, nullable=False)
    started_at = Column(String, nullable=True)
    finished_at = Column(String, nullable=True)
    log_path = Column(String, nullable=True)
    artifacts_path = Column(String, nullable=True)
    result_json = Column(Text, nullable=True)


class ScheduledRun(Base):
    __tablename__ = "scheduled_runs"

    id = Column(String, primary_key=True)
    campaign_id = Column(String, nullable=False, index=True)
    run_at = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="scheduled")  # scheduled|waiting_token|running|success|failed|canceled
    customer_name = Column(String, nullable=True, index=True)
    campaign_name = Column(String, nullable=True, index=True)
    token_plain = Column(String, nullable=True)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)

    # link to last Run id
    last_run_id = Column(String, nullable=True)
