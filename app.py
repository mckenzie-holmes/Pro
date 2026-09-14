from flask import Flask

app = Flask(__name__)


@app.route("/")
def home():
    return """
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Student Success Dashboard</title>
      </head>
      <body>
        <h1>Student Success Dashboard</h1>
        <p>Your academic command center is running.</p>
      </body>
    </html>
    """


if __name__ == "__main__":
    app.run(debug=True)
