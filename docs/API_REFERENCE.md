# QuizWeaver Web API Reference

This document describes the web endpoints available in QuizWeaver's Flask application.

---

## Authentication

All routes (except `/login`) require authentication. The web app uses session-based auth with default credentials:

- **Username:** `teacher`
- **Password:** `quizweaver`

Custom credentials can be set in `config.yaml`:

```yaml
auth:
  username: "your_username"
  password: "your_password"
```

### POST /login

Authenticate and create a session.

**Form Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `username` | string | Yes | Login username |
| `password` | string | Yes | Login password |

**Responses:**
- `303` -- Redirect to dashboard on success
- `401` -- Renders login page with error message

### GET /logout

Clear the session and redirect to login.

---

## Dashboard

### GET /dashboard

Renders the main dashboard with summary statistics.

**Template Variables:**
- `classes` -- List of all classes
- `total_classes` -- Integer count
- `total_lessons` -- Integer count
- `total_quizzes` -- Integer count
- `provider` -- Current LLM provider name

### GET /api/stats

Returns JSON data for dashboard charts.

**Response (200):**

```json
{
  "lessons_by_date": [
    {"date": "2026-01-15", "count": 3},
    {"date": "2026-01-16", "count": 1}
  ],
  "quizzes_by_class": [
    {"class_name": "7th Grade Science", "count": 5},
    {"class_name": "8th Grade Bio", "count": 2}
  ]
}
```

---

## Classes

### GET /classes

List all classes with lesson and quiz counts.

### GET /classes/new

Render the class creation form.

### POST /classes/new

Create a new class.

**Form Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Class name (e.g., "7th Grade Science - Block A") |
| `grade_level` | string | No | Grade level (e.g., "7th Grade") |
| `subject` | string | No | Subject area (e.g., "Science") |
| `standards` | string | No | Comma-separated standards (e.g., "SOL 7.1, SOL 7.2") |

**Responses:**
- `303` -- Redirect to class list on success
- `400` -- Renders form with error if name is empty

### GET /classes/:id

Show class detail page with assumed knowledge depth, recent lessons, and quizzes.

**URL Parameters:**
- `id` -- Class ID (integer)

**Response:** `404` if class not found.

### GET /classes/:id/edit

Render the class edit form with pre-filled values.

### POST /classes/:id/edit

Update class details.

**Form Parameters:** Same as POST /classes/new (all optional for update).

### POST /classes/:id/delete

Delete a class and all associated lesson logs.

**Response:** `303` redirect to class list, or `404` if not found.

---

## Lessons

### GET /classes/:id/lessons

List all lessons for a class with parsed topic lists.

### GET /classes/:id/lessons/new

Render the lesson logging form.

### POST /classes/:id/lessons/new

Log a new lesson for a class.

**Form Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string | Yes | Lesson content/summary text |
| `topics` | string | No | Comma-separated topics (auto-detected if omitted) |
| `notes` | string | No | Teacher notes about the lesson |

**Response:** `303` redirect to lesson list for the class.

### POST /classes/:id/lessons/:lesson_id/delete

Delete a specific lesson.

**Response:** `303` redirect to lesson list, or `404` if not found.

---

## Quizzes

### GET /quizzes

List all generated quizzes across all classes.

### GET /quizzes/:id

Show quiz detail with all questions and parsed answer data.

### GET /classes/:id/quizzes

List quizzes filtered to a specific class.

### GET /classes/:id/generate

Render the quiz generation form.

### POST /classes/:id/generate

Generate a new quiz using the AI pipeline.

**Form Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `num_questions` | integer | No | Number of questions (default: 20) |
| `grade_level` | string | No | Override grade level |
| `sol_standards` | string | No | Comma-separated SOL standards |

**Response:** `303` redirect to quiz detail on success, or renders form with error on failure.

---

## Costs

### GET /costs

Show API cost tracking dashboard with current provider info and usage statistics.

---

## Running the Server

```bash
python -c "from src.web.app import create_app; create_app().run(debug=False)"
```

The server starts at http://localhost:5000.
