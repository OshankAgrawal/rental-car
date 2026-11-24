from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Rental(Base):
    __tablename__ = "rentals"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    rental_id: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    vehicle_registration: Mapped[str] = mapped_column(String(30), nullable=False)
    customer_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    rental_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    damage_charge: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    total_charge: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR", server_default="INR")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    inspections: Mapped[list["Inspection"]] = relationship(
        back_populates="rental", cascade="all, delete-orphan"
    )
    reports: Mapped[list["Report"]] = relationship(
        back_populates="rental", cascade="all, delete-orphan"
    )


class Inspection(Base):
    __tablename__ = "inspections"
    __table_args__ = (
        UniqueConstraint("rental_id", "inspection_type", name="uq_rental_inspection_type"),
        CheckConstraint(
            "inspection_type IN ('pickup', 'return')",
            name="ck_inspection_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_inspection_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    rental_id: Mapped[str] = mapped_column(
        ForeignKey("rentals.rental_id", ondelete="CASCADE"), nullable=False, index=True
    )
    inspection_type: Mapped[str] = mapped_column(String(10), nullable=False)
    # Captured by the server when the employee records the pickup/return inspection.
    inspection_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    detection_json_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    rental: Mapped["Rental"] = relationship(back_populates="inspections")
    video: Mapped["Video | None"] = relationship(
        back_populates="inspection", cascade="all, delete-orphan", uselist=False
    )
    detections: Mapped[list["Detection"]] = relationship(
        back_populates="inspection", cascade="all, delete-orphan"
    )


class Video(Base):
    __tablename__ = "videos"
    __table_args__ = (
        UniqueConstraint("inspection_id", name="uq_video_per_inspection"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    inspection_id: Mapped[int] = mapped_column(
        ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    inspection: Mapped["Inspection"] = relationship(back_populates="video")


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    inspection_id: Mapped[int] = mapped_column(
        ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    frame_number: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    tracker_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    class_name: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    damage_charge: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # Bounding box and segmentation polygon are stored as JSON arrays.
    bbox_xyxy: Mapped[list | None] = mapped_column(JSON, nullable=True)
    segmentation_polygon: Mapped[list | None] = mapped_column(JSON, nullable=True)
    defect_frame_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    inspection: Mapped["Inspection"] = relationship(back_populates="detections")


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint("rental_id", "report_type", name="uq_rental_report_type"),
        CheckConstraint(
            "report_type IN ('pickup_inspection', 'return_inspection', 'final_comparison')",
            name="ck_report_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    rental_id: Mapped[str] = mapped_column(
        ForeignKey("rentals.rental_id", ondelete="CASCADE"), nullable=False, index=True
    )
    report_type: Mapped[str] = mapped_column(String(30), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    rental: Mapped["Rental"] = relationship(back_populates="reports")
