# Test Retake Feature

This feature allows teachers to generate a retake quiz while excluding questions from a previous version of the test.

## Setup

1.  **Dependencies:** Install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```
2.  **API Key:** Ensure you have a Google Gemini API key. Create a `.env` file in the root directory and add:
    ```
    GEMINI_API_KEY=your_api_key_here
    ```

## Usage

1.  **Input Content:**
    *   Place your content summary documents in the `Content_Summary` directory. Supported formats: `.pdf`, `.docx`, `.txt`.
    *   Images from these documents will be automatically extracted and used as context.

2.  **Retake Test Source:**
    *   Place the original test (as a PDF) in the `Retake` directory. The script reads this to:
        *   Exclude specific questions from the new quiz.
        *   Determine the default number of questions.
        *   Calculate the target percentage of questions that should include images.

3.  **Run the Script:**
    *   Default (uses counts from retake PDF):
        ```bash
        python main.py
        ```
    *   Specify question count manually:
        ```bash
        python main.py --count 20
        ```

4.  **Output:**
    *   The generated files are saved in the `Quiz_Output` directory.
    *   **QTI Zip:** `ChangeOverTime_Retake_YYYYMMDDHHMMSS.zip` (Import this into Canvas).
    *   **PDF Preview:** `ChangeOverTime_Retake_YYYYMMDDHHMMSS.pdf` (Review questions and answers).

## Features

*   **Intelligent Exclusion:** Scans the original test to prevent duplicate questions.
*   **Content-Based Generation:** Generates questions strictly based on the provided content summaries.
*   **Image Handling:**
    *   **Extraction:** Extracts images from source PDFs to use as context.
    *   **Generation:** If not enough extracted images are available to meet the target ratio, the script attempts to generate relevant images (or falls back to clear placeholders if the API is unavailable).
*   **Quality Assurance:** Adheres to `qa_guidelines.txt` for grade-appropriate rigor, question types (no fill-in-the-blank), and structure.
*   **Multi-Format Support:** Reads PDF, DOCX, and TXT files.

## Files

*   `main.py`: The core script for generating the quiz.
*   `qa_guidelines.txt`: Rules for the AI model regarding question quality and format.
*   `requirements.txt`: List of Python dependencies.
*   `Content_Summary/`: Directory for study guides/content summaries.
*   `Retake/`: Directory for the previous test PDF.
*   `Quiz_Output/`: Directory where the final QTI zip and PDF preview are saved.
