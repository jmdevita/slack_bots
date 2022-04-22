# Import and Dependancies
from flask_celery_app import flaskapp

# Grab Slack Apps
from support_team_bot_bp import support_bot_flow
from noodle_bot_bp import noodle_bot
from looker_users_bp import looker_bot
from who_is_this_bp import whoisthis_bot

# Register Blueprints
flaskapp.register_blueprint(support_bot_flow)
flaskapp.register_blueprint(noodle_bot)
flaskapp.register_blueprint(looker_bot)
flaskapp.register_blueprint(whoisthis_bot)

if __name__ == "__main__":
    flaskapp.run()