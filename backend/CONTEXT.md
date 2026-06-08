# Hajj Health Platform — Project Context

## What This System Does
A smart health monitoring platform for Hajj pilgrims.
The goal is to create a unified health record for each pilgrim,
predict health risks before and during Hajj, and help medical
teams respond faster and smarter.

## The 10 Tasks of This Platform
1. Platform dashboard and interface design
2. Data extraction from all file types and medical data unification
3. Pre-Hajj pilgrim risk classification model
4. Colored health card system based on risk level
5. Real-time health risk and crisis prediction during Hajj
6. Linking health data with environmental data and geolocation
7. Heat map showing pilgrim locations and risk levels
8. QR code system for quick access to health profiles
9. Automated alerts and instant medical recommendations
10. Communication system with real-time translation for pilgrims

## Current Focus
We are building Task 2 — Medical Data Unification.

### Data Sources
Source 1 — PDF or image from non-verified hospital
- Extract text → AI extracts JSON → confidence medium/low

Source 2 — QR from verified hospital
- QR contains patient_id only
- System fetches data from database by patient_id
- Confidence high → auto approved

### Build Order
Stage 5 → Stage 6 → Stage 7 → Stage 8 → Stage 9

## Important Notes
- Each pilgrim has one HealthProfile and multiple MedicalDocuments
- Extracted medical data must be structured as JSON
- Confidence scoring logic is defined in AGENTS.md
- Do not build frontend or APIs unless asked
- Work step by step following AGENTS.md