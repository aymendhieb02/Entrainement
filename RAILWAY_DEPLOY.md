# Push to GitHub & Deploy on Railway

## 1. Git configuration (one-time)

Open a terminal in the project folder and set your Git identity:

```bash
cd "c:\Users\Msi\OneDrive\Bureau\jawher\entrainement"

git config user.name "aymendhieb02"
git config user.email "aymen.dhieb@gmail.com"
```

To set this for all repos on your machine (optional):

```bash
git config --global user.name "aymendhieb02"
git config --global user.email "aymen.dhieb@gmail.com"
```

---

## 2. Push to GitHub (branch `main`)

### If this folder is not yet a Git repo

```bash
cd "c:\Users\Msi\OneDrive\Bureau\jawher\entrainement"

git init
git add .
git commit -m "Initial commit: Transformini Coach - biomechanics & rep counter"
git branch -M main
git remote add origin https://github.com/aymendhieb02/Entrainement.git
git push -u origin main
```

When prompted for credentials, use your GitHub username (`aymendhieb02`) and a **Personal Access Token** (not your GitHub password).  
To create a token: GitHub → Settings → Developer settings → Personal access tokens → Generate new token (classic), scope `repo`.

### If the folder is already a Git repo (e.g. cloned or existing .git)

```bash
cd "c:\Users\Msi\OneDrive\Bureau\jawher\entrainement"

git add .
git status
git commit -m "Your commit message"
git branch -M main
git remote remove origin
git remote add origin https://github.com/aymendhieb02/Entrainement.git
git push -u origin main
```

Use the same token as above when Git asks for a password.

---

## 3. Deploy on Railway

### 3.1 Create a Railway account

- Go to [https://railway.app](https://railway.app) (or Railway.ng if you use that).
- Sign up / log in (e.g. with GitHub).

### 3.2 New project from GitHub

1. In Railway dashboard: **New Project**.
2. Choose **Deploy from GitHub repo**.
3. Connect GitHub if needed and select the repo: **aymendhieb02/Entrainement**.
4. Branch: **main**.
5. Railway will detect:
   - **Python** (from `requirements.txt`)
   - **Web process** from `Procfile`: `web: gunicorn -b 0.0.0.0:$PORT main:app`
6. Click **Deploy**. Railway will build and run the app.

### 3.3 Get a public URL

1. In your project, open the **web** service.
2. Go to **Settings** → **Networking** → **Generate Domain** (or **Public Networking**).
3. Copy the URL (e.g. `https://your-app.up.railway.app`).

### 3.4 (Optional) Root directory

If the repo has multiple folders and the app is in a subfolder, set **Root Directory** in Railway to that folder (e.g. the folder that contains `main.py`, `Procfile`, `requirements.txt`). If everything is at the repo root, leave it empty.

### 3.5 Environment variables (optional)

In Railway: **Variables** tab. You usually don’t need any for this app.  
If you add a `.env` file later, add the same variables in Railway instead of committing `.env`.

---

## 4. What runs on Railway

- The **Flask app** runs with **gunicorn** and listens on `$PORT`.
- There is **no webcam** in the cloud, so the video feed shows a placeholder: *“Camera not available – run locally for live analysis.”*
- The rest of the UI (exercise list, categories, start/stop) works; only the live camera/pose analysis needs to be run **locally** with a camera.

---

## 5. Useful commands (later)

```bash
# Push new changes to GitHub (then Railway will auto-redeploy if connected)
git add .
git commit -m "Describe your changes"
git push origin main

# Check remotes
git remote -v
```

---

## 6. Checklist

- [ ] Git `user.name` and `user.email` set (aymendhieb02 / aymen.dhieb@gmail.com)
- [ ] Repo pushed to `https://github.com/aymendhieb02/Entrainement.git` on branch `main`
- [ ] Railway project created and connected to that GitHub repo
- [ ] Public domain generated and URL saved
- [ ] For live camera + pose analysis, run the app locally (`python main.py`)
