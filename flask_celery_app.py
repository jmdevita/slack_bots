import os, urllib.parse
from celery import Celery
from flask import Flask
from googleauthentication import googlesheets_append

BROKER_URL = "sqs://{aws_access_key}:{aws_secret_key}@".format(
    aws_access_key=urllib.parse.quote(os.environ['AWS_ACCESS_KEY'], safe=''), aws_secret_key=urllib.parse.quote(os.environ['AWS_SECRET_ACCESS_KEY'], safe='')
)
CELERY_BROKER_TRANSPORT_OPTIONS = {
    'region': 'sqs.us-west-1',
    'queue_name_prefix': 'celery-'
}


# Set up Flask app and Celery
flaskapp = Flask(__name__)
flaskapp.config['CELERY_BROKER_URL'] = BROKER_URL
celery = Celery(flaskapp.name, broker=flaskapp.config['CELERY_BROKER_URL'], transport=CELERY_BROKER_TRANSPORT_OPTIONS)
celery.conf.update(flaskapp.config)

# Set up Celery Tasks
@celery.task()
def add_user_google(googlesheets_id, email, requestor_name, requestor_id, group, _date):
    if ',' in email:
        emails = email.replace(' ','').split(',')
        for _email in emails:
            googlesheets_append(googlesheets_id, 'backlog!A:F', [_email, requestor_name, requestor_id, group, _date, "FALSE"])
    else:
        googlesheets_append(googlesheets_id, 'backlog!A:F', [email, requestor_name, requestor_id, group, _date, "FALSE"])