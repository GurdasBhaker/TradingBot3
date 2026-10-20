from TB2.Utilz.ai_dataclass import aikeys, x
import openai
import requests
from flask import Flask, request, jsonify

# === Keys ===
openai.api_key = aikeys.openai
bearer_token = x.bearer_token

app = Flask(__name__)
USERNAME = "realDonaldTrump"
USER_ID = None  # Cache after first call


# === Get Trump's User ID ===
def get_user_id():
    global USER_ID
    if USER_ID:
        return USER_ID
    url = f"https://api.twitter.com/2/users/by/username/{USERNAME}"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    USER_ID = r.json()['data']['id']
    return USER_ID


# === Get Latest Tweet ===
def get_latest_tweet():
    uid = get_user_id()
    url = f"https://api.twitter.com/2/users/{uid}/tweets?max_results=5&tweet.fields=created_at"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()['data'][0]['text']


# === Analyze via GPT ===
def analyze_tweet(tweet_text):
    prompt = f"""
Analyze this tweet for its likely effect on the U.S. stock market:

\"{tweet_text}\"

Respond with:
1. Market Sentiment: Positive / Negative / Neutral
2. Brief Reasoning:
"""
    res = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200
    )
    return res.choices[0].message['content']


# === Webhook for Pushcut to call ===
@app.route("/pushcut-trigger", methods=["POST"])
def pushcut_trigger():
    try:
        tweet = get_latest_tweet()
        gpt_response = analyze_tweet(tweet)
        print(f"\nNew Tweet: {tweet}\n\nMarket Sentiment:\n{gpt_response}\n{'-'*50}")
        return jsonify({"status": "ok", "tweet": tweet, "analysis": gpt_response})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# === Run server ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
