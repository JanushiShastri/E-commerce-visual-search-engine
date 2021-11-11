from app import app
import os

port = int(os.getenv("PORT"))
if __name__ == "__main__":
    app.run(host='http://127.0.0.1:5000/', port=port)
