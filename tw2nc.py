import caldav
import re
import urllib.request
import uuid
from bs4 import BeautifulSoup
from datetime import datetime
from icalendar import Calendar, Event

DATE_FORMAT = '%d.%m.%Y %H:%M'

sourceUrl = 'http://www.tanzschule-wehke.de/i/events'

username = ''
password = ''
nextcloudUrl = ''

calendar_name = 'Tanzschule'


def download_events():
    print("Downloading event page")

    response = urllib.request.urlopen(sourceUrl)
    html = response.read()

    print("Download successful (%s Bytes)" % len(html))

    return BeautifulSoup(html, 'html.parser').find_all('div', attrs={'class': 'newsFrame'})


def is_next_day_end(time):
    return time == '00:00'


def remove_whitespaces(text):
    return re.sub("\s\s+", " ", text.strip())


def is_abschlussball(title):
    return title == "Abschlussball"


def dtstart(event):
    return event.get('dtstart').dt.replace(tzinfo=None)


def dtend(event):
    return event.get('dtend').dt.replace(tzinfo=None)


def equal_event(left, right):
    return dtstart(left) == dtstart(right) and dtend(left) == dtend(right)


def first_event(cal):
    return cal.subcomponents[0]


def nextcloud_url():
    return 'https://%s:%s@%s' % (username, password, nextcloudUrl)


def target_calendar():
    client = caldav.DAVClient(nextcloud_url())
    principal = client.principal()
    calendars = principal.calendars()

    print("Found %s calendars at NextCloud" % len(calendars))

    for a_calendar in calendars:
        if a_calendar.name == calendar_name:
            return a_calendar


def create_event(p_title, p_date_start, p_date_end, p_description):
    cal = Calendar()
    cal.add('prodid', '-//tw2nc//1.0.0')
    cal.add('version', '2.0')

    event = Event()
    event.add('created', datetime.now())
    event.add('summary', p_title)
    event.add('dtstart', p_date_start)
    event.add('dtend', p_date_end)
    event.add('description', p_description)
    event.add('uid', str(uuid.uuid4()))
    cal.add_component(event)

    return cal


def is_event(p_component):
    return p_component.name == "VEVENT"


def find_existing_events(p_announced_events):
    events_from = dtstart(first_event(p_announced_events[0]))
    events_to = dtend(p_announced_events[len(p_announced_events) - 1].subcomponents[0])
    events = target_calendar.date_search(events_from, events_to)

    r_existing_events = list()

    for event in events:
        cal = Calendar.from_ical(event.data)

        for component in cal.walk():
            if is_event(component):
                r_existing_events.append(component)

    print("Found %s existing events" % len(r_existing_events))

    return r_existing_events


def find_announced_events():
    r_announced_events = list()

    for event in download_events():
        title = event.find('h2').text.strip()
        description = event.find('div').text.strip()
        text = remove_whitespaces(event.text)
        date_str = text[0:text.index(title) - 1]
        date_str_split = date_str.split(" ")

        date_start = datetime.strptime(date_str_split[1] + ' ' + date_str_split[3], DATE_FORMAT)

        if is_next_day_end(date_str_split[5]):
            date_end = datetime.strptime(date_str_split[1] + ' 23:59', DATE_FORMAT)
        else:
            date_end = datetime.strptime(date_str_split[1] + ' ' + date_str_split[5], DATE_FORMAT)

        if is_abschlussball(title):
            if is_wtp_2(event):
                title = title + " (F)"
            else:
                title = title + " (A)"

        r_announced_events.append(create_event(title, date_start, date_end, description))

    print("Found %s announced events" % len(r_announced_events))

    return r_announced_events


def is_wtp_2(event):
    for course in event.find_all('a', attrs={'class': 'plainlink'}):
        if course.text == "WTP 2":
            return True

    return False


def event_already_created(p_existing_events, p_announced_event):
    for existingEvent in p_existing_events:
        if equal_event(first_event(p_announced_event), existingEvent):
            return True

    return False


target_calendar = target_calendar()

announced_events = find_announced_events()
existing_events = find_existing_events(announced_events)

for announced_event in announced_events:
    if not event_already_created(existing_events, announced_event):
        print("Creating Event '%s'" % first_event(announced_event).get('summary'))
        target_calendar.add_event(announced_event.to_ical())
