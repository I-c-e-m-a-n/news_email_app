# News Email App

This project allows users to select a country and up to 4 news categories, then receive a curated email digest via Google News and Gmail.

## 🌐 Features
- React frontend (deployed via GitHub Pages)
- Python Flask backend for calling `fetch_and_email_news`
- User inputs: name, email, country, categories, Google News API key, Gmail credentials
- Emails curated news to users

## 📦 Structure
```
news-email-app/
├── frontend/           # React app (deployed on GitHub Pages)
├── backend/            # Flask API server (deploy on Render, Fly.io, etc.)
├── README.md
```

## 🚀 Frontend Deployment
```bash
cd frontend
npm install
npm run deploy
```
Make sure to edit:
- `vite.config.js` → set `base: '/<repo-name>/'`
- `package.json` → set correct `homepage`

## ⚙️ Backend Deployment
Install dependencies and run Flask server:
```bash
cd backend
pip install -r requirements.txt
python app.py
```
Deploy using Fly.io, Render, Railway, etc.

## 🔐 Notes
- Use [Gmail App Passwords](https://support.google.com/accounts/answer/185833) for security.
- Never expose `.env` or secrets in the frontend.

## 📬 API Example
Frontend sends a POST request to:
```
/send
```
With JSON payload:
```json
{
  "email": "user@example.com",
  "name": "Jane",
  "preferences": ["us", "World", "Health"],
  "api_key": "GOOGLE_NEWS_API_KEY",
  "gmail_user": "your@gmail.com",
  "gmail_pass": "your_app_password"
}
```

---