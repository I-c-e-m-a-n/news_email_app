from flask import Flask, request, jsonify
from bot_news_optimized import fetch_and_email_news

app = Flask(__name__)

@app.route("/send", methods=["POST"])
def send_news():
    try:
        data = request.json

        required_keys = ["email", "name", "preferences", "api_key", "gmail_user", "gmail_pass"]
        if not all(k in data for k in required_keys):
            return jsonify({"error": "Missing required fields"}), 400

        fetch_and_email_news(
            email=data["email"],
            name=data["name"],
            preferences=data["preferences"],
            api_key=data["api_key"],
            gmail_user=data["gmail_user"],
            gmail_pass=data["gmail_pass"]
        )

        return "Email sent successfully!"
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
