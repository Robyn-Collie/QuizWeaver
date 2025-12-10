# **🛡️ Ethical & Legal Guidelines for QuizWeaver**

As an educational AI tool, QuizWeaver is designed with strict adherence to data privacy, intellectual property rights, and pedagogical ethics. This document outlines the safeguards implemented in the system.

## **1\. Data Governance & Model Training (Critical)**

**Principle:** School data must never be used to train public AI models.

To ensure compliance with enterprise data standards, QuizWeaver distinguishes between **Development** and **Production** environments regarding API usage.

### **⚠️ API Tier Requirements**

* **Free Tier (Development Only):** Users utilizing free API keys (e.g., Google AI Studio Free Tier) acknowledge that their inputs and outputs **may be used** by model providers to train and improve their systems. This tier is strictly for testing with synthetic/dummy data.
* **Paid Tier (Classroom/Production):** For actual classroom use, QuizWeaver requires the use of **Paid API Tiers** (e.g., Google Cloud Vertex AI or OpenAI Enterprise).
  * **Google Gemini Policy:** As per Google's terms, data processed via **Paid Services** is **NOT** used to train their models.
  * **Zero Data Retention:** Production deployments must rely on these paid endpoints to guarantee that lesson content remains isolated to the user's environment.

## **2\. Student Data Privacy (FERPA/COPPA)**

**Principle:** QuizWeaver is a tool for *curriculum* generation, not *student* analysis. It should never process Personally Identifiable Information (PII).

### **Operational Guidelines**

* **Strict No-PII Input:** Users must NEVER upload documents containing student names, ID numbers, or completed worksheets.
* **Input Sanitization (Planned Feature):** Future versions will include a pre-processing hook (using libraries like Microsoft Presidio) to detect and reject input containing PII before it reaches the LLM.
* **Local-First Architecture:** To minimize data exposure, QuizWeaver stores parsed content in a local SQLite database (quiz\_warehouse.db) rather than a centralized cloud warehouse.

## **3\. Intellectual Property & Copyright**

**Principle:** We respect the rights of content creators. QuizWeaver assists teachers in creating *assessments* based on materials they are licensed to use.

### **Usage Rules**

* **Fair Use Scope:** This tool is intended for creating derivative assessments for direct classroom use, aligning with standard educational Fair Use provisions.
* **Textbook Material:** Users are advised against processing entire commercial textbooks. Best practice is to input teacher-created summaries, notes, or specific relevant excerpts.

## **4\. AI Safety & Bias Mitigation**

**Principle:** Educational assessments must be factually accurate, culturally neutral, and accessible.

### **The "Critic Agent" Safeguard**

The QuizWeaver pipeline includes a dedicated **Critic Agent** that reviews every generated question before it is presented to the user. This agent is prompted to check for:

1. **Hallucinations:** Verifying that the question answers can actually be derived from the source text.
2. **Cultural Bias:** Ensuring names and scenarios used in word problems are inclusive and non-stereotypical.
3. **Accessibility:** Verifying that language complexity matches the target grade level (e.g., 7th Grade).

## **5\. Human-in-the-Loop (HITL)**

**Principle:** AI is a drafter, not a publisher.

* **Mandatory Review:** The default output format is a "Draft PDF" or "QTI Package" intended for teacher review. The system does not directly administer quizzes to students.
* **Traceability:** The system logs which source file was used to generate specific questions, allowing teachers to verify the source of truth.

*This document is a living part of the QuizWeaver engineering standard.*
