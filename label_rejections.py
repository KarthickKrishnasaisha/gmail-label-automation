from __future__ import print_function
import os.path
from typing import List

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# This scope lets us read and modify Gmail labels
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']


def get_gmail_service():
    """Authenticate and return a Gmail API service object."""
    creds = None

    # token.json stores the user's access and refresh tokens.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If there are no (valid) credentials, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('gmail', 'v1', credentials=creds)
    return service


def get_or_create_label(service, label_name: str) -> str:
    """Return the label ID for label_name, creating it if needed."""
    results = service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])

    for label in labels:
        if label['name'].lower() == label_name.lower():
            print(f"Found existing label '{label_name}' with ID: {label['id']}")
            return label['id']

    # If not found, create the label
    label_body = {
        'name': label_name,
        'labelListVisibility': 'labelShow',
        'messageListVisibility': 'show'
    }

    created_label = service.users().labels().create(
        userId='me', body=label_body
    ).execute()

    print(f"Created label '{label_name}' with ID: {created_label['id']}")
    return created_label['id']


def search_messages(service, query: str) -> List[str]:
    """
    Search for messages using a Gmail search query.
    Returns a list of message IDs.
    """
    message_ids = []
    request = service.users().messages().list(userId='me', q=query)

    while request is not None:
        response = request.execute()
        messages = response.get('messages', [])
        for m in messages:
            message_ids.append(m['id'])

        request = service.users().messages().list_next(
            previous_request=request,
            previous_response=response
        )

    print(f"Found {len(message_ids)} messages matching the query.")
    return message_ids


def add_label_to_messages(service, message_ids: List[str], label_id: str):
    """Add the given label to all messages in message_ids."""
    if not message_ids:
        print("No messages to label.")
        return

    # Gmail batchModify can handle up to 1000 IDs at a time
    chunk_size = 1000
    for i in range(0, len(message_ids), chunk_size):
        chunk = message_ids[i:i + chunk_size]
        body = {
            'ids': chunk,
            'addLabelIds': [label_id],
            'removeLabelIds': []
        }
        service.users().messages().batchModify(
            userId='me', body=body
        ).execute()
        print(f"Labeled {len(chunk)} messages in this batch.")


def main():
    service = get_gmail_service()

    # 1) Ensure we have a label called "rejections"
    label_name = "rejections"
    label_id = get_or_create_label(service, label_name)

    # 2) Gmail search query to find likely rejection emails
    # You can tweak this based on real phrases in your inbox.
    query = (
    'in:inbox ('
    '"we regret to inform you" OR '
    '"we are unable to move forward" OR '
    '"we have decided not to move forward" OR '
    '"you were not selected" OR '
    '"Thank you for your interest in" OR '
    '"Thank you for applying to"'
    ')'
)


    # 3) Find all matching messages
    message_ids = search_messages(service, query=query)

    # 4) Apply the "rejections" label to them
    add_label_to_messages(service, message_ids, label_id)

    print("Done! All matching emails have been labeled as 'rejections'.")


if __name__ == '__main__':
    main()
