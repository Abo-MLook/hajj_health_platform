from django.contrib import admin

from .models import HealthProfile, MedicalDocument, Pilgrim


@admin.register(Pilgrim)
class PilgrimAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "patient_id",
        "passport_number",
        "nationality",
        "gender",
        "date_of_birth",
        "phone",
        "hajj_permit_number",
        "created_at",
    )
    search_fields = (
        "full_name",
        "patient_id",
        "passport_number",
        "nationality",
        "phone",
        "hajj_permit_number",
    )
    list_filter = ("nationality", "gender", "created_at")


@admin.register(HealthProfile)
class HealthProfileAdmin(admin.ModelAdmin):
    list_display = (
        "pilgrim",
        "status",
        "confidence_score",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "pilgrim__full_name",
        "pilgrim__passport_number",
        "diseases_text",
        "medications_text",
        "allergies_text",
        "vaccinations_text",
    )
    list_filter = ("status", "confidence_score", "created_at", "updated_at")


@admin.register(MedicalDocument)
class MedicalDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "pilgrim",
        "original_filename",
        "file_type",
        "status",
        "confidence_score",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "pilgrim__full_name",
        "pilgrim__passport_number",
        "original_filename",
        "file_type",
        "extracted_text",
    )
    list_filter = ("status", "file_type", "confidence_score", "created_at", "updated_at")
