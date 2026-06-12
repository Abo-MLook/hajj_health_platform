import uuid
from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models

MAX_DOCUMENT_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def pilgrim_document_upload_path(instance, filename):
    return f"uploads/pilgrims/{instance.pilgrim_id}/{filename}"


def validate_file_size(value):
    if value.size > MAX_DOCUMENT_FILE_SIZE:
        raise ValidationError("File size must not exceed 10MB.")


def generate_patient_id():
    return uuid.uuid4().hex[:12].upper()


class Pilgrim(models.Model):
    GENDER_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
    ]

    full_name = models.CharField(max_length=255)
    patient_id = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        default=generate_patient_id,
        editable=False,
    )
    passport_number = models.CharField(max_length=100, unique=True, db_index=True)
    nationality = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    hajj_permit_number = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def age(self):
        """Current age in years derived from date_of_birth, or None if unknown."""
        if not self.date_of_birth:
            return None
        today = date.today()
        born = self.date_of_birth
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

    def __str__(self):
        return f"{self.full_name} - {self.passport_number}"


class HealthProfile(models.Model):
    pilgrim = models.OneToOneField(
        Pilgrim,
        on_delete=models.CASCADE,
        related_name="health_profile",
    )
    diseases_text = models.TextField(blank=True)
    medications_text = models.TextField(blank=True)
    allergies_text = models.TextField(blank=True)
    vaccinations_text = models.TextField(blank=True)
    status = models.CharField(max_length=30, default="pending")
    confidence_score = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Health profile for {self.pilgrim.full_name}"


class MedicalDocument(models.Model):
    pilgrim = models.ForeignKey(
        Pilgrim,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    file = models.FileField(
        upload_to=pilgrim_document_upload_path,
        validators=[
            FileExtensionValidator(allowed_extensions=["pdf", "jpg", "jpeg", "png"]),
            validate_file_size,
        ],
    )
    file_type = models.CharField(max_length=100, blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    extracted_text = models.TextField(blank=True)
    extracted_json = models.JSONField(null=True, blank=True)
    confidence_score = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=30, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.original_filename or self.file.name
