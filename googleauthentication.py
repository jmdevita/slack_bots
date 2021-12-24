from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import os, json
import boto3

session = boto3.Session(
    aws_access_key_id=os.environ['AWS_ACCESS_KEY'],
    aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
    region_name='us-west-1'
)


s3 = session.resource('s3')

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

SAMPLE_SPREADSHEET_ID = '1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms'
SAMPLE_RANGE_NAME = 'Class Data!A2:E'

obj = s3.Object('looker-user', 'token.json')
token_obj = json.loads(obj.get()['Body'].read())

if isinstance(token_obj, str):
    token_obj = json.loads(token_obj)

if token_obj != None:
  creds = Credentials.from_authorized_user_info(token_obj, SCOPES)
else:
  creds = None
# If there are no (valid) credentials available, let the user log in.
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        print("Refreshing Token")
        creds.refresh(Request())
    else:
        raise SystemExit('There is no token.json file')
        
    # Save the credentials for the next run
    s3object = s3.Object('looker-user', 'token.json')
    s3object.put(
        Body=(bytes(json.dumps(creds.to_json()).encode('UTF-8')))
    )

#### Functions ####
def googlesheets_read(spreadsheetId=SAMPLE_SPREADSHEET_ID,rangeId=SAMPLE_RANGE_NAME):

    service = build('sheets', 'v4', credentials=creds)

    # Call the Sheets API
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=spreadsheetId,
                                range=rangeId).execute()
    values = result.get('values', [])

    return values

def googlesheets_append(spreadsheetId=SAMPLE_SPREADSHEET_ID,range=SAMPLE_RANGE_NAME, cell_values="Updated"):

    service = build('sheets', 'v4', credentials=creds)

    # Call the Sheets API
    values = [
            cell_values
        # Additional rows ...
    ]
    body = {
        'values': values
    }

    request = service.spreadsheets().values().append(spreadsheetId=spreadsheetId, range=range, valueInputOption= "RAW", insertDataOption="INSERT_ROWS", body=body)
    response = request.execute()

    return response

def googlesheets_massupdate(spreadsheetId=SAMPLE_SPREADSHEET_ID,rangeId=SAMPLE_RANGE_NAME, cell_values="Updated"):

    service = build('sheets', 'v4', credentials=creds)

    # Call the Sheets API
    batch_update_values_request_body = {
        # How the input data should be interpreted.
        'value_input_option': "USER_ENTERED",  # TODO: Update placeholder value.
        # The new values to apply to the spreadsheet.
        'data': [{
            "range": rangeId,
            "values": cell_values
        }],

        #"responseValueRenderOption": "FORMULA",
    }

    request = service.spreadsheets().values().batchUpdate(spreadsheetId=spreadsheetId, body=batch_update_values_request_body)
    response = request.execute()

def googlesheets_clear(spreadsheetId=SAMPLE_SPREADSHEET_ID, rangeId="*"):
    service = build('sheets', 'v4', credentials=creds)

    result = service.spreadsheets().values().clear(spreadsheetId=spreadsheetId,
                                range=rangeId).execute()

def googlesheets_write(spreadsheetId=SAMPLE_SPREADSHEET_ID,rangeId=SAMPLE_RANGE_NAME, cell_value="Updated"):
    service = build('sheets', 'v4', credentials=creds)

    # Call the Sheets API
    values = [
        [
            cell_value
        ],
        # Additional rows ...
    ]
    body = {
        'values': values
    }
    result = service.spreadsheets().values().update(
        spreadsheetId=spreadsheetId, range=rangeId,
        valueInputOption="USER_ENTERED", body=body).execute()