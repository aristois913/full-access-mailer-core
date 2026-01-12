# Technical Deep-Dive

## A. Bot Interface (__main__.py)
The "Command & Control" (C2) is handled through Telegram.
- Template Injection: The /template command allows the attacker to upload an HTML file, which is then stored in a local JSON database.
- Session Management: The /auth command takes an email and password, validates the format, and tests the IMAP connection in real-time.
- Admin Hierarchy: It includes an "Operator" menu for managing a whitelist of Telegram IDs, effectively turning this into a "Phishing-as-a-Service" (PhaaS) platform.

## B. Mail Engine (core/mail.py)
This is the most critical part for Gmail/Yahoo to see.
- MIME Construction: It uses MIMEMultipart to build the email structure.
- Headers: The template method creates standard Subject, From, Reply-To, and To headers, but because it is injected via IMAP, the "Sender" IP often appears as the user's legitimate IP or the attacker's server IP, rather than a known spam relay.

## C. Data Storage (core/user.py & db.json)
The tool uses a flat-file JSON database to store state.
- Credential Harvesting: It stores pairs of email: password for various compromised accounts.
- Template Persistence: The phishing HTML is stored directly inside the template field in the JSON structure.

## D. Database Schema (db.json)
The storage structure is designed for multi-tenancy (Phishing-as-a-Service). The schema includes:
- admin (bool): Distinguishes between the kit operator and "sub-users".
- emails (dict): A map of compromised credentials stored in plain text.
- template (str): The base64 or raw HTML string injected into the MIMEText body.

## E. C2 Command Reference (Telegram Interface)
The bot acts as a Command & Control (C2) hub. Each command is designed to manage the "Full-Access" lifecycle from credential testing to template injection.

| Command | Role | Action |
| --- | --- | --- |
| `/start` | Initialization | Registers the user session and checks against the whitelist in db.json. |
| `/auth <email> <pass>` | Cred Validation | Instantiates a MailSender object. Attempts an immediate IMAP login to verify credentials for Gmail, AOL, or Yahoo. |
| `/template` | Payload Delivery | Awaits a file upload. Once received, the bot reads the HTML/Text content and stores it in the template field of the user's database entry. |
| `/sendmail` | Execution | The core "attack" command. It uses shlex to parse arguments (Subject, From Name, etc.) and triggers the IMAP Append process. |
| `/emails` | Asset Management | Returns a list of all successfully authenticated accounts currently "warm" in the database. |
| `/delmail` | Asset Cleanup | Removes specific compromised credentials from the db.json cache. |
| `/operator` | Admin Control | Exclusive to users with admin: true. Allows whitelisting/blacklisting other Telegram IDs (PhaaS management). |