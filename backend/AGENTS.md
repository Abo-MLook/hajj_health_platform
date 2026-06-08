# Hajj Health Platform - Codex Instructions

## Project Overview
This is a Django backend for a Hajj health platform.

The goal is to create a unified health profile for each pilgrim by collecting health data from:
1. Manual health form input
2. Medical PDF/image uploads
3. QR verification later
4. External health API later

The system will later extract diseases, medications, allergies, vaccinations, and risk factors from uploaded files.

## Current Project Structure
- Django project is inside backend/
- Main config folder is config/
- Apps are stored inside apps/
- Pilgrims app path is apps/pilgrims/
- Use app config path: apps.pilgrims.apps.PilgrimsConfig

## Development Rules
- Work step by step.
- Do not jump ahead.
- Do not create frontend unless I ask.
- Do not create APIs unless I ask.
- Do not create templates unless I ask.
- Before editing, explain which files will be changed.
- After editing, show a short summary and commands run.
- Keep changes small and focused.
- Prefer Django best practices.
- Do not delete files without asking.
- Do not rename folders without asking.

## Current Backend Goal
Build the backend in stages:

### Stage 1
Create Django app setup for apps/pilgrims.

### Stage 2
Create database models:
- Pilgrim
- HealthProfile
- MedicalDocument

### Stage 3
Create admin registration.

### Stage 4
Create file upload handling.

## Updated Stage Plan

### Stage 5
Extract raw text from PDF and image files.
- Use pdfplumber for PDF
- Use pytesseract for images (Arabic + English)
- Save extracted text to MedicalDocument.extracted_text

### Stage 6
Use AI to extract structured medical JSON from raw text.
- Send extracted text to AI
- Get back structured JSON with diseases, medications, 
  allergies, vaccinations
- Save to MedicalDocument.extracted_json

### Stage 7
Add confidence scoring:
- QR verified = 1.0
- Clear PDF = 0.75
- Image = 0.50
- Conflicting data = needs_review

### Stage 8
QR Code system:
- QR contains patient_id only
- System fetches health profile by patient_id
- Use pyzbar + Pillow only (not opencv)

### Stage 9
Merge all sources into unified HealthProfile.

## Medical Logic
The platform should store:
- pilgrim identity
- chronic diseases
- current medications
- medication dose/frequency
- allergies
- vaccinations
- uploaded medical documents
- extracted text
- extracted JSON
- confidence score
- review status

## Confidence Logic
Use these statuses:
- pending
- approved
- needs_review
- rejected

Basic confidence idea:
- Official API = highest confidence
- Verified QR = high confidence
- Clear PDF from known medical source = medium/high confidence
- Image prescription only = medium confidence
- Manual pilgrim input only = low confidence
- Conflicting data = needs_review

## Important
Always keep the project focused on backend first.
