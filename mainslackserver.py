# Import and Dependancies
from dotenv import load_dotenv
from flask_celery_app import flaskapp

load_dotenv()

# Grab Slack Apps
from support_team_bot_bp import support_bot_flow
from noodle_bot_bp import noodle_bot
from looker_users_bp import looker_bot

# Register Blueprints
flaskapp.register_blueprint(support_bot_flow)
flaskapp.register_blueprint(noodle_bot)
flaskapp.register_blueprint(looker_bot)

if __name__ == "__main__":
    flaskapp.run()