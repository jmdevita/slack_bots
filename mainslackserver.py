# Import and Dependancies
from flask import Flask
import os
from slack_sdk import WebClient

# Grab Slack Apps
from support_team_bot_bp import support_bot_flow
from noodle_bot_bp import noodle_bot

app = Flask(__name__)
app.register_blueprint(support_bot_flow)
app.register_blueprint(noodle_bot)

if __name__ == "__main__":
    app.run()
