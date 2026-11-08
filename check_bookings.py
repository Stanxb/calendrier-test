# check_bookings.py
import json, os, smtplib, urllib.request
from datetime import timedelta
from email.mime.text import MIMEText
from icalendar import Calendar, Event

BOOKING_ICAL = os.environ["BOOKING_ICAL_URL"]
GMAIL = os.environ["GMAIL_ADDRESS"]
GMAIL_PASS = os.environ["GMAIL_APP_PASSWORD"]
SEEN_FILE = "seen.json"
BLOCK_FILE = "docs/blocked.ics"

def fetch_bookings():
    data = urllib.request.urlopen(BOOKING_ICAL).read()
    cal = Calendar.from_ical(data)
    out = []
    for ev in cal.walk("VEVENT"):
        out.append({
            "uid": str(ev.get("UID")),
            "start": ev.get("DTSTART").dt,
            "end": ev.get("DTEND").dt,
        })
    return out

def send_email(text):
    msg = MIMEText(text)
    msg["Subject"] = "Nouvelle réservation Booking"
    msg["From"] = GMAIL
    msg["To"] = GMAIL
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(GMAIL, GMAIL_PASS)
        s.send_message(msg)

def main():
    seen = json.load(open(SEEN_FILE)) if os.path.exists(SEEN_FILE) else []
    bookings = fetch_bookings()

    for b in bookings:
        if b["uid"] not in seen:
            co = b["end"].strftime("%d/%m/%Y")
            send_email(f"Nouvelle réservation ! Check-out le {co}, "
                       f"ménage à prévoir ce jour-là.")
            seen.append(b["uid"])

    cal = Calendar()
    cal.add("prodid", "-//Blocage menage//FR")
    cal.add("version", "2.0")
    for b in bookings:
        ev = Event()
        ev.add("uid", b["uid"] + "-block")
        ev.add("summary", "Bloque apres check-out")
        ev.add("dtstart", b["end"])
        ev.add("dtend", b["end"] + timedelta(days=2))
        cal.add_component(ev)

    os.makedirs("docs", exist_ok=True)
    open(BLOCK_FILE, "wb").write(cal.to_ical())
    json.dump(seen, open(SEEN_FILE, "w"))

if __name__ == "__main__":
    main()
