# Installing QuizWeaver

A step-by-step guide for getting QuizWeaver running on your computer. No programming experience required -- this only takes about 5 minutes.

---

## What You'll Need

- **A computer** running Windows 10 or newer, macOS 10.15 (Catalina) or newer, or Linux
- **Python 3.9 or newer** (free -- we'll walk you through installing it)
- **An internet connection** for the first-time setup (to download the software libraries QuizWeaver depends on)
- **About 5 minutes** of your time

That's it. QuizWeaver runs entirely on your computer. There is no cloud account to create, no subscription to sign up for, and no credit card required.

---

## Step 1: Install Python

Python is the programming language QuizWeaver is built with. You need it installed on your computer, but you do not need to learn it -- think of it like installing Java to run Minecraft.

### Windows

1. Open your web browser and go to [python.org/downloads](https://www.python.org/downloads/)
2. Click the big yellow **"Download Python 3.x.x"** button
3. Open the downloaded file to start the installer
4. **IMPORTANT: On the very first screen of the installer, check the box that says "Add Python to PATH"** -- this is the most common source of problems, and it's easy to miss

   ```
   [x] Add Python to PATH     <--- CHECK THIS BOX
   ```

5. Click **"Install Now"**
6. Wait for the installation to finish, then click **"Close"**

**What you should see:** The installer finishes with a "Setup was successful" message.

### macOS

**Option A -- Using Homebrew** (if you already have Homebrew installed):

1. Open the **Terminal** app (search for "Terminal" in Spotlight, or find it in Applications > Utilities)
2. Type the following and press Enter:
   ```
   brew install python3
   ```

**Option B -- Using the installer from python.org:**

1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Click the big yellow **"Download Python 3.x.x"** button
3. Open the downloaded `.pkg` file and follow the installer prompts

### Linux (Ubuntu / Debian)

Open a terminal and run:

```
sudo apt update && sudo apt install python3 python3-pip python3-venv
```

### Verify Python is Installed

After installing, let's make sure it worked.

**Windows:**
1. Press the Windows key, type `cmd`, and press Enter to open Command Prompt
2. Type the following and press Enter:
   ```
   python --version
   ```

**macOS / Linux:**
1. Open the Terminal app
2. Type the following and press Enter:
   ```
   python3 --version
   ```

**What you should see:** A version number, like:

```
Python 3.11.5
```

The number after "Python" should start with 3.9 or higher (3.9, 3.10, 3.11, 3.12, 3.13 -- any of these are fine).

If you see an error like `'python' is not recognized`, see the Troubleshooting section below.

---

## Step 2: Download QuizWeaver

### Option A: Download as a ZIP File (Recommended)

This is the simplest approach -- no special tools needed.

1. Go to [github.com/Robyn-Collie/QuizWeaver](https://github.com/Robyn-Collie/QuizWeaver)
2. Click the green **"Code"** button near the top of the page
3. Click **"Download ZIP"**
4. Find the downloaded ZIP file (usually in your Downloads folder) and extract it:
   - **Windows:** Right-click the ZIP file and choose **"Extract All..."**, then click **"Extract"**
   - **macOS:** Double-click the ZIP file -- it will extract automatically
   - **Linux:** Right-click and choose **"Extract Here"**, or run `unzip QuizWeaver-main.zip`
5. Move the extracted folder somewhere convenient, like your Desktop or Documents folder

**What you should see:** A folder called `QuizWeaver-main` (or `QuizWeaver`) containing files like `run.bat`, `run.sh`, `config.yaml`, `requirements.txt`, and folders like `src/` and `tests/`.

### Option B: Clone with Git (If You Know Git)

If you have Git installed and know how to use it, you can clone the repository. "Cloning" means downloading the project along with its full change history, which makes updating easier later.

Open a terminal or command prompt and run:

```
git clone https://github.com/Robyn-Collie/QuizWeaver.git
```

This creates a `QuizWeaver` folder in your current location.

---

## Step 3: Start QuizWeaver

This is where the launcher scripts do the heavy lifting. They handle everything automatically: installing libraries, setting up the database, and opening the app in your browser.

### Windows

1. Open the QuizWeaver folder you extracted in Step 2
2. Find the file called **`run.bat`**
3. **Double-click `run.bat`**

A black window (Command Prompt) will open and you'll see progress messages. On the first run, it will install the necessary software libraries -- this takes about 1-2 minutes. After that, your web browser will open automatically to QuizWeaver.

**What you should see in the Command Prompt window:**

```
  ============================================
   QuizWeaver - Language-Model-Assisted
   Teaching Platform
  ============================================

  [OK] Found Python 3.11.5
  [OK] Dependencies already installed

  Starting QuizWeaver...
  Your browser will open automatically.
```

**What you should see in your browser:** The QuizWeaver login page at the address `http://localhost:5000`.

> **Note:** The black Command Prompt window must stay open while you use QuizWeaver. Minimizing it is fine -- just don't close it. It's the "engine" running in the background.

### macOS / Linux

1. Open the **Terminal** app
2. Navigate to the QuizWeaver folder. If you extracted it to your Desktop, type:
   ```
   cd ~/Desktop/QuizWeaver-main
   ```
   (Adjust the path if you put the folder somewhere else.)
3. The first time, make the launcher script executable, then run it:
   ```
   chmod +x run.sh && ./run.sh
   ```
4. On future runs, you only need:
   ```
   ./run.sh
   ```

On the first run, the script creates a virtual environment (an isolated space for QuizWeaver's libraries so they don't interfere with anything else on your computer) and installs dependencies. This takes about 1-2 minutes. After that, your browser will open automatically.

**What you should see in the terminal:**

```
  ============================================
   QuizWeaver - Language-Model-Assisted
   Teaching Platform
  ============================================

  [OK] Found Python 3.11.5
  [OK] Virtual environment active
  [OK] Dependencies already installed

  Starting QuizWeaver...
  Your browser will open automatically.
```

**What you should see in your browser:** The QuizWeaver login page at `http://localhost:5000`.

> **Note:** Keep the terminal window open while you use QuizWeaver. You can minimize it, but closing it will stop the app.

---

## Step 4: First-Time Setup

When you open QuizWeaver for the first time, the app walks you through a short setup process.

### Create Your Account

1. You'll see a registration screen asking for a **username** and **password**
2. Pick something you'll remember -- this account is stored only on your computer, not in any cloud service
3. Click **Create Account**, then sign in

### Onboarding Wizard

After signing in, a setup wizard guides you through:

1. **Creating your first class** -- Enter a name (like "Period 1 - US History" or "Block A - English 10") and optionally a grade level
2. **Choosing your language model provider** -- The default is **"Mock"**, which is a built-in practice mode that generates sample content at zero cost with no internet connection needed. This is perfect for exploring the platform. You can connect a real provider later if you choose.

**What you should see:** After the wizard, you arrive at your QuizWeaver dashboard, ready to start creating quizzes, study materials, and lesson plans.

### About Mock Mode

QuizWeaver starts in **Mock mode** by default. This means:

- All language model features work, but the generated text comes from built-in templates rather than an external service
- It costs nothing -- no API keys, no accounts, no charges
- It works completely offline (after the first-time setup)
- It's a great way to explore every feature before deciding whether to connect a real provider

You can use Mock mode for as long as you like. There is no trial period or expiration.

---

## Connecting a Real Language Model Provider (Optional)

If you'd like the generated content (quiz questions, study materials, lesson plans) to be more contextually relevant to your actual lessons, you can connect a real language model provider.

### How to Connect

1. Open QuizWeaver and sign in
2. Go to **Settings** (gear icon in the navigation bar)
3. Find the **Provider Setup Wizard** section
4. Follow the on-screen steps for your chosen provider

### Recommended Provider

**Google Gemini** is the recommended starting point:
- Google offers a free tier that is sufficient for typical teacher usage
- Setup requires creating a free Google API key
- The Provider Setup Wizard in QuizWeaver walks you through the process step by step

### Other Supported Providers

- **Anthropic Claude** -- Strong reasoning and long context, via Anthropic API or Google Cloud Vertex AI
- **Google Vertex AI** -- For schools with Google Cloud accounts (supports both Gemini and Claude models)
- **OpenAI** -- GPT-4o and other OpenAI models
- **Ollama** -- Run language models entirely on your own computer, with no data sent anywhere (requires separate Ollama installation)

### Cost Transparency

When you use a real provider, QuizWeaver shows you the estimated cost before each operation and tracks your spending. You stay in control of how much you spend. The Settings page displays cost summaries so there are never surprise charges.

---

## Stopping and Restarting

### How to Stop QuizWeaver

- **Windows:** Close the black Command Prompt window, or click inside it and press `Ctrl+C`
- **macOS / Linux:** Go to the terminal window and press `Ctrl+C`

### How to Restart QuizWeaver

Just run the launcher again:
- **Windows:** Double-click `run.bat`
- **macOS / Linux:** Run `./run.sh` from the terminal

Everything picks up right where you left off. Your classes, quizzes, lessons, and settings are all saved.

### Where Is My Data Stored?

Your data lives in a file called **`quiz_warehouse.db`** inside the QuizWeaver folder. This is a SQLite database -- a single file that contains all your classes, quizzes, lessons, and settings. It never leaves your computer.

If you ever need to back up your work, simply copy the `quiz_warehouse.db` file to a safe location (like a USB drive or cloud storage folder).

---

## Troubleshooting

### "Python is not recognized as an internal or external command" (Windows)

This means Python was installed without being added to your system's PATH. The fix:

1. Uninstall Python: Open **Settings > Apps**, find Python, click **Uninstall**
2. Re-download the installer from [python.org/downloads](https://www.python.org/downloads/)
3. Run the installer again, and this time **check the "Add Python to PATH" box** on the very first screen
4. Restart your computer
5. Try again: open Command Prompt and type `python --version`

### "Permission denied" when running `run.sh` (macOS / Linux)

The script needs permission to run. In your terminal, navigate to the QuizWeaver folder and run:

```
chmod +x run.sh
```

Then try again:

```
./run.sh
```

### "Address already in use" or "Port 5000 already in use"

Another program is using port 5000 on your computer. Common causes:

- **macOS:** AirPlay Receiver uses port 5000 by default. Go to **System Settings > General > AirDrop & Handoff** and turn off **AirPlay Receiver**. Then try again.
- **Another instance of QuizWeaver:** Make sure you don't have QuizWeaver running in another terminal window. Close it first.
- **Another application:** Close whatever else might be using port 5000, or wait a moment and try again.

### Dependencies won't install / "pip" errors

Try upgrading pip first. Open Command Prompt (Windows) or Terminal (macOS/Linux) and run:

**Windows:**
```
python -m pip install --upgrade pip
```

**macOS / Linux:**
```
python3 -m pip install --upgrade pip
```

Then try running the launcher script again.

### The browser didn't open automatically

If the launcher says "Starting QuizWeaver..." but no browser window appeared, you can open it manually. Open any web browser and go to:

```
http://localhost:5000
```

### QuizWeaver was working yesterday but won't start today

1. Make sure no other instance of QuizWeaver is already running (check for open Command Prompt or terminal windows)
2. Try running the launcher script again
3. If the error mentions the database, your `quiz_warehouse.db` file may have been corrupted. Rename it to `quiz_warehouse_backup.db` and run the launcher again -- QuizWeaver will create a fresh database. You can ask for help recovering data from the backup.

---

## Updating QuizWeaver

When a new version is released, updating is straightforward. Your data is preserved across updates.

### If You Downloaded the ZIP File

1. Download the latest ZIP from [github.com/Robyn-Collie/QuizWeaver](https://github.com/Robyn-Collie/QuizWeaver)
2. Extract it to a new folder (like `QuizWeaver-new`)
3. Copy your **`quiz_warehouse.db`** file from the old QuizWeaver folder into the new one
4. (Optional) Copy your **`config.yaml`** if you customized any settings
5. Start QuizWeaver from the new folder using `run.bat` or `run.sh`
6. The first run after an update may take an extra minute to install any new dependencies

### If You Used Git Clone

Open a terminal in your QuizWeaver folder and run:

```
git pull
```

Then start QuizWeaver normally. The launcher will install any new dependencies automatically.

### What Gets Preserved

- **quiz_warehouse.db** -- All your classes, quizzes, lessons, standards, rubrics, and settings
- **config.yaml** -- Your configuration (provider settings, preferences)
- **Quiz_Output/** -- Any exported quizzes (PDFs, DOCX files, etc.)

### What Gets Updated

- Source code in `src/`
- Templates and prompts
- Static files (CSS, JavaScript)
- Migration scripts (database updates run automatically on next launch)

---

## Docker Installation (For IT Administrators)

If you are deploying QuizWeaver for multiple teachers across a school or district, Docker provides a way to run it as a shared service on a server. This section is intended for IT staff -- teachers can skip it.

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/) installed on the server

### Quick Start

From the QuizWeaver project folder, run:

```
docker compose up -d
```

This builds and starts QuizWeaver in the background. The app will be available at `http://your-server-address:8000`.

### Configuration

Set environment variables to customize the deployment:

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `change-me-in-production` | Session encryption key. **Change this for production.** |
| `LLM_PROVIDER` | `mock` | Language model provider (`mock`, `gemini`, `anthropic`, `vertex`, `openai`, `openai-compatible`) |
| `DATABASE_PATH` | `/app/data/quiz_warehouse.db` | Path to the SQLite database inside the container |

Example with a custom secret key:

```
SECRET_KEY=your-secure-random-string docker compose up -d
```

### Data Persistence

The Docker setup uses named volumes to preserve data between container restarts:

- **qw-data** -- Database and application data
- **qw-images** -- Generated images

### Stopping

```
docker compose down
```

Your data is preserved in the Docker volumes and will be available when you start again.

### Dockerfile and Docker Compose Reference

- **`Dockerfile`** -- Defines the container image (Python 3.11, dependencies, health check)
- **`docker-compose.yml`** -- Defines the service, ports, volumes, and environment variables

---

## Getting Help

If you run into a problem not covered here:

1. Check the [Troubleshooting](#troubleshooting) section above
2. Look at the [GitHub Issues page](https://github.com/Robyn-Collie/QuizWeaver/issues) to see if someone has reported the same problem
3. Open a new issue on GitHub describing what happened, what you expected, and any error messages you saw

---

*QuizWeaver is a language-model-assisted teaching platform. The language model writes; the rules verify; the teacher decides.*
