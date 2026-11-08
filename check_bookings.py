import json, os, smtplib, urllib.request
from datetime import date, datetime, timedelta, timezone
from email.mime.text import MIMEText
from icalendar import Calendar, Event

BOOKING_ICAL = os.environ["BOOKING_ICAL_URL"]
GMAIL = os.environ["GMAIL_ADDRESS"]
GMAIL_PASS = os.environ["GMAIL_APP_PASSWORD"]
SEEN_FILE = "seen.json"
ACTIVE_FILE = "active.json"
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

def send_email(subject, text):
    msg = MIMEText(text)
    msg["Subject"] = subject
    msg["From"] = GMAIL
    msg["To"] = GMAIL
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(GMAIL, GMAIL_PASS)
        s.send_message(msg)

def overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end

def main():
    seen = json.load(open(SEEN_FILE)) if os.path.exists(SEEN_FILE) else []
    old_active = json.load(open(ACTIVE_FILE)) if os.path.exists(ACTIVE_FILE) else {}
    bookings = fetch_bookings()
    current_uids = {b["uid"] for b in bookings}
    today = date.today().isoformat()

    # Réservations annulées
    for uid, info in old_active.items():
        if uid not in current_uids and info["end"] > today:
            co = date.fromisoformat(info["end"]).strftime("%d/%m/%Y")
            send_email("Réservation annulée",
                       f"Bonjour, la réservation avec check-out le {co} "
                       f"a été annulée. Pas besoin de prévoir le nettoyage "
                       f"ce jour-là. Merci !")

    # Nouvelles réservations
    for b in bookings:
        if b["uid"] not in seen:
            co = b["end"].strftime("%d/%m/%Y")
            send_email("Nouvelle réservation Booking",
                       f"Bonjour, on a un nouveau check-out le {co}. "
                       f"Est-ce que vous pouvez prévoir un nettoyage "
                       f"pour ce jour-là ? Merci !")
            seen.append(b["uid"])

    cal = Calendar()
    cal.add("prodid", "-//Blocage menage//FR")
    cal.add("version", "2.0")

    for b in bookings:
        blocks = [
            ("avant", b["start"] - timedelta(days=1), b["start"]),
            ("apres", b["end"], b["end"] + timedelta(days=2)),
        ]
        for label, s, e in blocks:
            conflict = any(
                o["uid"] != b["uid"] and overlaps(s, e, o["start"], o["end"])
                for o in bookings
            )
            if conflict:
                key = f"alert-{b['uid']}-{label}"
                if key not in seen:
                    send_email("Blocage impossible",
                               f"Le blocage {label} la réservation "
                               f"du {b['start'].strftime('%d/%m/%Y')} au "
                               f"{b['end'].strftime('%d/%m/%Y')} n'a pas pu "
                               f"se faire : ces jours sont déjà réservés.")
                    seen.append(key)
                continue
            ev = Event()
            ev.add("uid", f"{b['uid']}-block-{label}")
            ev.add("dtstamp", datetime.now(timezone.utc))
            ev.add("summary", f"Bloque {label}")
            ev.add("dtstart", s)
            ev.add("dtend", e)
            cal.add_component(ev)

    new_active = {b["uid"]: {"end": b["end"].isoformat()[:10]} for b in bookings}

    os.makedirs("docs", exist_ok=True)
    open(BLOCK_FILE, "wb").write(cal.to_ical())
    json.dump(seen, open(SEEN_FILE, "w"))
    json.dump(new_active, open(ACTIVE_FILE, "w"))

if __name__ == "__main__":
    main()
