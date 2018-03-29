"""
built off work here: https://www.fullstackpython.com/blog/build-first-slack-bot-python.html
"""

import os
import re
import requests
import time
import json

from mapbox import Geocoder
from slackclient import SlackClient

# instantiate Slack client and Mapbox geocoding client
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))
geocoder = Geocoder()

# get mapbox access token from environement variable
MAPBOX_ACCESS_TOKEN = os.environ.get('MAPBOX_ACCESS_TOKEN')

# mapbot's user ID in Slack: value is assigned after the bot starts up
mapbot_id = None

# constants
RTM_READ_DELAY = 1 # 1 second delay between reading from RTM
EXAMPLE_COMMAND = "map Washington, DC"
MENTION_REGEX = "^<@(|[WU].+?)>(.*)"
BASE_URL = 'https://api.mapbox.com'
STATIC_URL = BASE_URL + '/styles/v1/mapbox/streets-v10/static'

def handle_failure(query):
    """
        Handle any failed searches
    """
    return "Sorry, we're having trouble finding {query}. Can you be more specific?".format(query=query)

def parse_bot_commands(slack_events):
    """
        Parses a list of events coming from the Slack RTM API to find bot commands.
        If a bot command is found, this function returns a tuple of command and channel.
        If its not found, then this function returns None, None.
    """
    for event in slack_events:
        if event["type"] == "message" and not "subtype" in event:
            user_id, message = parse_direct_mention(event["text"])
            if user_id == mapbot_id:
                return message, event["channel"]
    return None, None

def parse_direct_mention(message_text):
    """
        Finds a direct mention (a mention that is at the beginning) in message text
        and returns the user ID which was mentioned. If there is no direct mention, returns None
    """
    matches = re.search(MENTION_REGEX, message_text)
    # the first group contains the username, the second group contains the remaining message
    return (matches.group(1), matches.group(2).strip()) if matches else (None, None)

def handle_command(command, channel):
    """
        Executes bot command if the command is known
    """
    # Default response is help text for the user
    default_response = "Not sure what you mean. Try *{}*.".format(EXAMPLE_COMMAND)

    # Finds and executes the given command, filling in response
    response = None
    attachment = None

    if command.startswith("locate"):
        query_list = command.split(" ")
        query = " ".join(query_list[1:])
        response = get_coords(query)

    if command.startswith("map"):
        query_list = command.split(" ")
        query = " ".join(query_list[1:])
        response, attachment = get_static_map(query)

    # Sends the response back to the channel
    slack_client.api_call(
        "chat.postMessage",
        channel=channel,
        text=response or default_response,
        attachments=attachment
    )

def get_static_map(query):
    """
        Generate a static map image with a marker
    """
    # get center coordinates
    latlon = get_coords(query)

    # construct url
    marker_url = '/pin-s-heart+285A98({lat},{lon})'.format(lat=latlon[0],lon=latlon[1])
    location_url = '/{lat},{lon},14,0,60/600x600?access_token={token}'.format(lat=latlon[0],lon=latlon[1],token=MAPBOX_ACCESS_TOKEN)

    # generate url and make request
    request_url = STATIC_URL + marker_url + location_url
    response = requests.get(request_url)

    if response.status_code:
        address = get_address(query)
        attachment = generate_attachments(request_url)
        if address and attachment:
            return "We found {query} at {address}".format(query=query, address=address), attachment
        else:
            return handle_failure(query), None
    else:
        return handle_failure(query), None

def generate_attachments(url):
    """
        Generate the attachment for the Slack message
    """
    return [{"title": "", "image_url": url}]

def get_coords(query):
    """
        Return the coordinates of the first query result
    """
    response = geocoder.forward(query)
    if response.status_code and len(response.geojson()['features']) >= 1:
        first = response.geojson()['features'][0]
        return first['geometry']['coordinates']
    else:
        return handle_failure(query)

def get_address(query):
    """
        Return the place name of the first query result
    """
    response = geocoder.forward(query)
    if response.status_code and len(response.geojson()['features']) >= 1:
        first = response.geojson()['features'][0]
        print(first['place_name'])
        return first['place_name']
    else:
        return None

if __name__ == "__main__":
    if slack_client.rtm_connect(with_team_state=False):
        print("Mapbot connected and running!")
        # Read bot's user ID by calling Web API method `auth.test`
        mapbot_id = slack_client.api_call("auth.test")["user_id"]
        while True:
            command, channel = parse_bot_commands(slack_client.rtm_read())
            if command:
                handle_command(command, channel)
            time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed. Exception traceback printed above.")
