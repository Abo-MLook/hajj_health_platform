# Hajj Health Platform

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-4.2%2B-green.svg)](https://www.djangoproject.com/)
[![Gemini AI](https://img.shields.io/badge/AI-Gemini%20AI-orange.svg)](https://deepmind.google/technologies/gemini/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A smart health monitoring and risk prediction platform for Hajj pilgrims. The platform is designed to establish unified health records for pilgrims, predict health risks before and during Hajj, and help medical teams respond faster and smarter to medical crises.

---

## 🌟 Key Capabilities

### 1. Unified Health Profiles
Aggregates and merges multi-source medical data into a single, reliable health profile for each pilgrim:
*   **Manual Inputs:** Forms filled out directly by the pilgrim.
*   **Medical Document Uploads:** PDFs and image scans of prescriptions, lab reports, or hospital discharges.
*   **Verified QR Codes:** Instant scanning to retrieve authenticated patient data.
*   **External Health APIs:** Seamless integration with official healthcare databases.

### 2. Intelligent Data Extraction & Verification
Converts raw files and scans into structured, searchable health data:
*   **Bilingual OCR:** Extracts English and Arabic text from scanned images and PDFs using advanced optical character recognition.
*   **AI-Driven Structuring:** Parses raw, unstructured medical texts with Gemini AI to identify chronic diseases, medications (with dosage and frequency), allergies, and vaccinations.
*   **Source Confidence Scoring:** Scores and ranks data reliability. Authenticated hospital QR scans receive instant approval, while manual inputs or uploaded images get lower confidence scores and are automatically queued for review if conflicts arise.

### 3. Real-Time Risk Monitoring & Mapping
Empowers organizers and medical teams with interactive insights:
*   **Pre-Hajj Risk Classification:** Groups pilgrims by health risk severity.
*   **Colored Health Card System:** Visual badge representation of risk level.
*   **Environmental & Geolocation Mapping:** Links health data with geolocation and environmental conditions (such as heat indexes or crowd density).
*   **Risk Heat Maps:** Provides live maps tracking pilgrim locations and high-risk zones.

### 4. Smart Emergency & Translation Response
Assists responders at critical moments:
*   **Offline-Ready QR Verification:** Quick QR lookup to access a pilgrim's emergency details immediately.
*   **Instant Alerts & Recommendations:** Dispatches immediate health recommendations and alerts to responders.
*   **Bilingual Translation:** Cross-language translation capabilities allowing medical staff to communicate with pilgrims from all over the world.

---

## 🛠️ Technology Stack
*   **Framework:** Django (Python)
*   **AI Integration:** Gemini API (Google DeepMind)
*   **OCR:** `pytesseract` (for image text extraction) & `pdfplumber` (for PDF text extraction)
*   **QR Processing:** `pyzbar` & `Pillow`
*   **Cloud Storage:** Cloudinary (for secure medical document hosting)
*   **Database:** SQLite (Default for development)

---

## 📂 Project Structure
```text
hajj_health_platform/
├── backend/
│   ├── apps/
│   │   └── pilgrims/         # Main application for pilgrim profiles, OCR, and AI pipeline
│   ├── config/               # Project configuration, settings, and routing
│   ├── manage.py             # Django CLI manager
│   ├── uploads/              # Local uploads folder (for development)
│   └── .env                  # Environment secrets (API Keys, etc.)
└── venv/                     # Python virtual environment
```

---

## 🚀 Getting Started

### Prerequisites
*   Python 3.10 or higher
*   Tesseract OCR engine installed on your system (required for image processing)

### Setup & Installation

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/yourusername/hajj_health_platform.git
    cd hajj_health_platform
    ```

2.  **Activate Virtual Environment:**
    *   **Windows:**
        ```powershell
        .\venv\Scripts\activate
        ```
    *   **macOS/Linux:**
        ```bash
        source venv/bin/activate
        ```

3.  **Install Dependencies:**
    ```bash
    pip install -r backend/requirements.txt
    ```

4.  **Configure Environment Variables:**
    Create a `.env` file inside the `backend/` directory with the following variables:
    ```env
    GEMINI_API_KEY=your_gemini_api_key
    CLOUDINARY_CLOUD_NAME=your_cloudinary_cloud_name
    CLOUDINARY_API_KEY=your_cloudinary_api_key
    CLOUDINARY_API_SECRET=your_cloudinary_api_secret
    ```

5.  **Run Migrations:**
    ```bash
    python backend/manage.py migrate
    ```

6.  **Start Development Server:**
    ```bash
    python backend/manage.py runserver
    ```
    Access the system locally at `http://127.0.0.1:8000/`.
