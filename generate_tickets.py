#!/usr/bin/env python3
"""Generate a SYNTHETIC, labelled IT-ticket benchmark (seeded, reproducible).

Why it exists: public IT-ticket data is hard to get and unlabelled. This file builds a test set
with known answers so the triage tool can be scored. It is deliberately NOT easy:
  - typos, vague wording, and paraphrases that avoid the tool's keywords
  - security incidents described WITHOUT obvious security words (the tool should struggle)
  - harmless tickets that contain scary words (false-alarm bait)
  - outages, empty-ish tickets, and mixed-signal tickets
The tool's rules were NOT tuned on this file. Results show pipeline behaviour, not real-world accuracy.

Run:     python3 generate_tickets.py [--set heldout]
Writes:  synthetic_data/synthetic_tickets.csv   (same columns as the public dataset layout)
         synthetic_data/synthetic_labels.csv    (ticket_id, title, preview, true_category)
"""
import csv
import os
import random
import re

SYSTEMS = ["payroll system", "CRM", "intranet", "Jira", "SharePoint", "Teams", "expenses portal", "HR portal"]
APPS = ["Excel", "Adobe Reader", "Zoom", "Slack", "Chrome", "Photoshop", "Visio", "Power BI"]
OFFICES = ["Dubai", "London", "Lagos", "Singapore"]

# (title, content, true_category). {s}=system {a}=app {o}=office {n}=number
CLEAN = [
 ("Locked out of my account", "I typed the wrong password too many times and now my account is locked.", "Access / Password"),
 ("Password reset needed", "Forgot my password for the {s}, can you reset it please?", "Access / Password"),
 ("MFA not working", "The authenticator app shows a code but the {s} rejects it every time.", "Access / Password"),
 ("Access denied on {s}", "Since this morning I get 'access denied' on the {s}.", "Access / Password"),
 ("VPN keeps dropping", "The VPN disconnects every few minutes when I work from home.", "Network / VPN"),
 ("No wifi in room {n}", "Wifi in meeting room {n} says connected but pages never load.", "Network / VPN"),
 ("DNS error", "I get a DNS error on every site from the {o} office.", "Network / VPN"),
 ("Outlook calendar not syncing", "My shared mailbox calendar invites are not showing up.", "Email / Calendar"),
 ("Missing email attachments", "Attachments in my inbox show as empty files.", "Email / Calendar"),
 ("Mailbox full", "My mailbox is full and I can't receive new mail.", "Email / Calendar"),
 ("Laptop battery drains fast", "My laptop battery lasts under an hour and the charger gets very hot.", "Hardware"),
 ("Monitor flickering", "The monitor at my desk flickers every few seconds.", "Hardware"),
 ("Printer offline", "The printer on floor {n} shows offline for everyone near me.", "Hardware"),
 ("Keyboard keys stuck", "Several keys on my keyboard are stuck.", "Hardware"),
 ("Install {a}", "Please install {a} on my machine. No rush.", "Software / Application"),
 ("{a} crashes", "{a} crashes every time I try to export a file.", "Software / Application"),
 ("Licence expired for {a}", "My licence for {a} expired this week, how can I renew it?", "Software / Application"),
 ("How do I book a meeting room?", "Question: what is the process for booking a room in the {o} office?", "General request"),
 ("Remote work policy question", "Would like to know what equipment I can claim for working from home.", "General request"),
 ("Request for training", "Is there any training available on the {s}?", "General request"),
]
PARAPHRASE = [  # no obvious keywords: the rules are expected to be unsure
 ("Thrown out of {s}", "Every time I open the {s} it sends me back to the start page.", "Access / Password"),
 ("New starter blocked", "Just joined the team and the shared folder says I am not allowed in.", "Access / Password"),
 ("Nothing loads", "Pages hang forever at my desk, colleagues nearby seem fine.", "Network / VPN"),
 ("Can't reach the office systems", "From home I cannot reach any of the internal sites since yesterday.", "Network / VPN"),
 ("Not receiving anything", "People say they sent me documents yesterday but I have received nothing.", "Email / Calendar"),
 ("Won't switch on", "My machine will not turn on this morning, no lights at all.", "Hardware"),
 ("Fan is deafening", "The fan in my machine is incredibly loud and it feels hot.", "Hardware"),
 ("Spreadsheet takes ages", "{a} takes several minutes to open my usual files.", "Software / Application"),
 ("Need a tool", "I need something to edit PDFs for a project next week.", "Software / Application"),
]
SECURITY_OBVIOUS = [
 ("Phishing email", "I received a phishing email pretending to be HR and I clicked the link.", "Security incident"),
 ("Unauthorized login alert", "I got an alert for an unauthorized login to my account from another country.", "Security incident"),
 ("Malware warning", "My laptop shows a malware warning and files are being renamed.", "Security incident"),
 ("Think I was hacked", "I think my account was hacked, my password stopped working and emails went out.", "Security incident"),
]
SECURITY_DISGUISED = [  # real incidents WITHOUT the usual security words
 ("Odd message from IT", "Got a text from 'IT' asking me to confirm my credentials on a page. I typed them in before realising.", "Security incident"),
 ("Call from the bank", "A caller said they were from our bank and asked me to read out the code from my authenticator app.", "Security incident"),
 ("Messages I never wrote", "My chat account sent messages to clients that I never wrote.", "Security incident"),
 ("Found a USB stick", "Found a USB stick in the car park, plugged it into my laptop and now it behaves strangely.", "Security incident"),
 ("Invoice looked off", "I paid an invoice today but the supplier says the bank details we used were not theirs.", "Security incident"),
]
SCARY_BUT_BENIGN = [  # contain security words, are routine
 ("Virus definitions update failed", "The virus definitions update failed on my laptop. Could you check the update?", "Software / Application"),
 ("Access to breach response runbook", "Please can I get access to the breach response runbook for the on-call rota?", "Access / Password"),
 ("Security awareness training", "How do I enrol in the security awareness training? I couldn't find the link on the {s}.", "General request"),
]
OUTAGE = [
 ("Everyone cannot connect", "Everyone in the {o} office cannot connect to the VPN, it is an outage.", "Network / VPN"),
 ("Whole team locked out", "The whole team is locked out of the {s}, urgent.", "Access / Password"),
]
VAGUE = [
 ("Help", "Something is wrong, please look.", "Other / Unclear"),
 ("Urgent!!!", "", "Other / Unclear"),
 ("Issue", "It happened again.", "Other / Unclear"),
]
MIXED = [  # two issues in one ticket; label = the main complaint
 ("Outlook crashes", "Outlook crashes on launch and shows an error with my mailbox.", "Email / Calendar"),
 ("Laptop and password", "My laptop screen is cracked and I also forgot my password.", "Hardware"),
]
GROUPS = [(CLEAN, 135), (PARAPHRASE, 60), (SECURITY_OBVIOUS, 14), (SECURITY_DISGUISED, 20),
          (SCARY_BUT_BENIGN, 12), (OUTAGE, 10), (VAGUE, 15), (MIXED, 14)]


# ---------------- HELD-OUT BANK: different wording, written separately, used only to MEASURE ----------------
CLEAN_H = [
 ("Cannot log into {s}", "The {s} keeps saying my details are incorrect even after I reset it.", "Access / Password"),
 ("Temporary password expired", "The temporary password I was given has expired before I could use it.", "Access / Password"),
 ("Wi-Fi drops in {o} office", "The wifi in the {o} office keeps dropping out through the day.", "Network / VPN"),
 ("Slow VPN", "VPN is connected but extremely slow for file transfers.", "Network / VPN"),
 ("Cannot send email", "Outlook says my message could not be sent to external addresses.", "Email / Calendar"),
 ("Out of office not working", "My automatic replies in Outlook are not being sent.", "Email / Calendar"),
 ("Docking station issue", "My docking station does not detect the second monitor.", "Hardware"),
 ("Headset no sound", "The headset has no sound in calls.", "Hardware"),
 ("{a} won't update", "The update for {a} keeps failing at 40 percent.", "Software / Application"),
 ("{a} licence request", "Please install {a} and assign me a licence for the new project.", "Software / Application"),
 ("Where to find IT policies?", "Question: where can I find the acceptable use policy?", "General request"),
 ("Loan laptop", "Would like to know if loan laptops are available for travel.", "General request"),
]
PARAPHRASE_H = [
 ("Shut out", "The system just refuses to let me through since the weekend.", "Access / Password"),
 ("Dead zone", "There is no signal anywhere near the back of the {o} office.", "Network / VPN"),
 ("Can't see messages", "The folder where my client messages go is empty but it shouldn't be.", "Email / Calendar"),
 ("Screen goes black", "The display goes black after a few minutes and I need to wiggle the cable.", "Hardware"),
 ("Slow to start", "{a} takes forever to start since the last update.", "Software / Application"),
]
SECURITY_OBVIOUS_H = [
 ("Ransomware note on screen", "A ransomware message appeared and my files are locked.", "Security incident"),
 ("Account compromised", "I believe my account is compromised, there are logins I do not recognise.", "Security incident"),
 ("Stolen laptop", "My laptop was stolen from my car last night.", "Security incident"),
]
SECURITY_DISGUISED_H = [
 ("Helpdesk called me", "Someone rang claiming to be from the helpdesk and wanted me to install a tool so they could see my screen.", "Security incident"),
 ("Boss wants vouchers", "An email from my director asks me to buy gift vouchers urgently and send her the codes.", "Security incident"),
 ("Approval pop-ups", "My phone keeps showing sign-in approval requests overnight that I did not start.", "Security incident"),
 ("Scary pop-up", "A pop-up said my computer is infected and told me to call a number to fix it.", "Security incident"),
 ("Unknown device on my profile", "My profile shows a sign-in from a device in another country that is not mine.", "Security incident"),
 ("Files renamed", "All my documents now end in .locked and there is a text file asking for payment.", "Security incident"),
]
SCARY_BUT_BENIGN_H = [
 ("Malware training slides", "Can you share the slides from last week's malware awareness session? I missed it.", "General request"),
 ("Reset VPN credentials", "My contractor needs new VPN credentials for the {s}, please issue them.", "Access / Password"),
 ("Update bank details", "How do I update my bank details in the expenses portal?", "General request"),
 ("USB port dead", "The USB port on my laptop is dead, nothing is recognised.", "Hardware"),
]
OUTAGE_H = [
 ("Site down", "The {s} is down for all users in {o}.", "Software / Application"),
 ("Wifi outage", "Total wifi outage on floor {n}, whole office affected.", "Network / VPN"),
]
VAGUE_H = [
 ("Not working", "It is not working again.", "Other / Unclear"),
 ("Please call me", "Call me back when you can.", "Other / Unclear"),
 ("Hi", "", "Other / Unclear"),
]
MIXED_H = [
 ("Email and printer", "Printer is offline and I also cannot open my mailbox.", "Hardware"),
]
GROUPS_H = [(CLEAN_H, 120), (PARAPHRASE_H, 50), (SECURITY_OBVIOUS_H, 12), (SECURITY_DISGUISED_H, 24),
            (SCARY_BUT_BENIGN_H, 24), (OUTAGE_H, 8), (VAGUE_H, 12), (MIXED_H, 10)]
BANKS = {"main": (GROUPS, 7, "synthetic"), "heldout": (GROUPS_H, 11, "heldout")}


def typo(text, rng):
    words = text.split()
    idx = [i for i, w in enumerate(words) if len(w) > 4 and w.isalpha()]
    if not idx:
        return text
    i = rng.choice(idx)
    w = words[i]
    k = rng.randrange(1, len(w) - 1)
    words[i] = w[:k] + w[k + 1] + w[k] + w[k + 2:]
    return " ".join(words)


def fill(text, rng):
    return (text.replace("{s}", rng.choice(SYSTEMS)).replace("{a}", rng.choice(APPS))
            .replace("{o}", rng.choice(OFFICES)).replace("{n}", str(rng.randint(1, 9))))


def generate(seed=7, groups=None):
    rng = random.Random(seed)
    items = []
    for templates, count in (groups or GROUPS):
        for _ in range(count):
            title, content, label = rng.choice(templates)
            title, content = fill(title, rng), fill(content, rng)
            if rng.random() < 0.15:
                content = typo(content, rng)
            items.append((title, content, label))
    rng.shuffle(items)
    tickets, labels = [], []
    for n, (title, content, label) in enumerate(items, 1):
        tid = f"SYN-{n:04d}"
        tickets.append([tid, title, content, rng.choice(["Open", "Closed"]), f"user_{rng.randint(100, 999)}", rng.randint(0, 30)])
        labels.append([tid, title, re.sub(r"\s+", " ", content)[:160], label])
    return tickets, labels


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Generate a synthetic labelled ticket benchmark.")
    ap.add_argument("--set", choices=list(BANKS), default="main",
                    help="'main' = the benchmark used while building; 'heldout' = fresh wording used only to measure")
    groups, seed, prefix = BANKS[ap.parse_args().set]
    tickets, labels = generate(seed, groups)
    os.makedirs("synthetic_data", exist_ok=True)
    with open(f"synthetic_data/{prefix}_tickets.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Ticket No.", "Title", "Content", "Status", "Author", "Age"])
        w.writerows(tickets)
    with open(f"synthetic_data/{prefix}_labels.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["ticket_id", "title", "preview", "true_category"])
        w.writerows(labels)
    print(f"Wrote {len(tickets)} synthetic tickets and labels to synthetic_data/{prefix}_*.csv")


if __name__ == "__main__":
    main()
