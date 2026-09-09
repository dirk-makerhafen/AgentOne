#!/usr/bin/env python
import datetime
from email import policy
from email.header import decode_header, make_header
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime
import os
from pathlib import Path
import re
import shutil
from subprocess import PIPE, Popen
import textwrap
import unicodedata
import email.utils
import html2text
import yaml
from bs4 import BeautifulSoup  # pip install beautifulsoup4

def clean_filename(raw: str, max_len: int = 150, fallback: str = "unnamed") -> str:
    '''Return an ASCII-only, filesystem- and pipeline-safe file/folder name.

    The AppleScript exporter only strips ``/ : \\ * ? " < > |`` and truncates
    to 150 chars (possibly splitting emoji), so sender/subject-derived names
    can still contain emoji, non-Latin scripts, control chars or newlines,
    which break git, shell tools and downstream parsing later. This maps
    everything to ``[A-Za-z0-9@._-]``:

    1. German umlauts transliterated (ae/oe/ue/ss, existing convention).
    2. NFKD decomposition + strip combining marks (e -> e, n -> n, ...).
    3. Drop whatever is still non-ASCII (emoji, CJK, zero-width chars, ...).
    4. Replace any remaining unsafe char (incl. whitespace, newlines,
       brackets, slashes) with ``_``, then fold ``._`` into ``_``
       (period-space artifacts like ``bald._Jetzt``). Runs of 3+
       underscores collapse to one — but a double ``__`` is kept as-is,
       since the mail exporter uses it as the date/sender/subject
       separator. Strip leading dots/dashes/underscores (hidden files,
       ``..``) and trailing dots (Windows-unfriendly).
    5. Truncate to ``max_len`` chars; empty results become ``fallback``.
    '''
    name = raw or ""
    name = name.replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue')
    name = name.replace('Ä', 'Ae').replace('Ö', 'Oe').replace('Ü', 'Ue')
    name = name.replace('ß', 'ss')
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = name.encode("ascii", "ignore").decode("ascii")
    name = re.sub(r'[^A-Za-z0-9@._-]+', '_', name)
    name = name.replace('._', '_')
    name = re.sub(r'_{3,}', '_', name)
    name = re.sub(r'-+', '-', name)
    name = re.sub(r'\.+', '.', name)
    # Dot-collapse can re-create "._" (e.g. "3D_..._3D" -> "3D_._3D"),
    # and folding can rebuild 3+ runs — repeat both once to a fixpoint
    # (no later step creates dots or underscores, so two passes settle).
    name = name.replace('._', '_')
    name = re.sub(r'_{3,}', '_', name)
    # The dash/underscore mix rules feed each other in a single pass
    # (e.g. "X__-10" -> "X_-10", which still contains "_-"; "a-_-_b"
    # -> "a--b", which needs a dash re-collapse), so loop to a fixpoint.
    # Every hit strictly shortens the string, so this always terminates —
    # and it makes the function idempotent.
    prev = None
    while prev != name:
        prev = name
        name = re.sub(r'-+', '-', name)
        name = re.sub(r'_-_', '-', name)
        name = re.sub(r'-_-', '-', name)
        name = re.sub(r'_-', '-', name)
        name = re.sub(r'-_', '-', name)
    name = name.strip('._- ')

    if not name:
        name = fallback
    if len(name) > max_len:
        name = name[:max_len].rstrip('._- ')
        if not name:
            name = fallback
    return name


def clean_attachment_name(filename: str, max_stem_len: int = 150) -> str:
    '''Clean an email attachment filename, preserving a safe extension.'''
    raw = (filename or "").strip().replace("\x00", "")
    # Senders sometimes ship full client paths ("C:\\docs\\file.pdf").
    raw = re.split(r'[\\/]', raw)[-1]
    suffix = Path(raw).suffix  # keeps the last ".ext"
    stem = raw[: -len(suffix)] if suffix else raw
    clean_stem = clean_filename(stem, max_len=max_stem_len, fallback="attachment")
    clean_suffix = re.sub(r'[^A-Za-z0-9]+', '', suffix[1:] if suffix else "")
    if clean_suffix:
        clean_suffix = "." + clean_suffix.lower()
    return clean_stem + clean_suffix


def sync(account: str, target_folder, git_autocommit=True) -> list[str]|str:
    '''
    sync specific mailbox by email adress, returns a list of eml files
    '''

    OUTPUT_PATH = Path(target_folder).resolve()   
    WORKING_PATH = OUTPUT_PATH / ".exporting" # A subfolder for clarity
    WORKING_PATH.mkdir(exist_ok=True, parents=True)
    stateFilePath = OUTPUT_PATH/  f".{account}_min_ts.txt"
    if not stateFilePath.exists():
        stateFilePath.write_text(f"%s" % int(datetime.datetime.now().timestamp() - (26*365*24*60*60)))
    
    while True:
        script = f'''
        set exportFolderPath to "{WORKING_PATH.as_posix()}/"
        set stateFilePath to "{stateFilePath.as_posix()}"
        set accountName to "{account}"
        ''' 

        script += r'''
        -- === HELPER ===
        on ensureFolderExists(thePath)
            do shell script "mkdir -p " & quoted form of thePath
        end ensureFolderExists

        on readTimestampFromFile(thePath)
    
            set unixTime to (do shell script "cat " & quoted form of thePath) as integer
            set nowUnix to (do shell script "date +%s") as integer
            set secondsDiff to nowUnix - unixTime
            return (current date) - secondsDiff
        
        end readTimestampFromFile

        on sanitize(theText)
            set illegalChars to {"/", ":", "\\", "*", "?", "\"", "<", ">", "|"}
            set cleanText to theText
            repeat with char in illegalChars
                set AppleScript's text item delimiters to char
                set theList to text items of cleanText
                set AppleScript's text item delimiters to "_"
                set cleanText to theList as string
            end repeat
            -- Limit length to avoid path errors
            if length of cleanText > 150 then set cleanText to text 1 thru 150 of cleanText
            return cleanText
        end sanitize

        on makeSafeMailID(mailboxName, m)
            tell application "Mail"
                set msgSubject to my sanitize(subject of m)
                set msgSender to my sanitize(extract address from sender of m)
                try
                    set msgDate to date sent of m
                on error
                    set msgDate to date received of m
                end try
            end tell
            
            set y to year of msgDate as text
            set mo to text -2 thru -1 of ("0" & (month of msgDate as integer))
            set d to text -2 thru -1 of ("0" & day of msgDate)
            set h to text -2 thru -1 of ("0" & hours of msgDate)
            set mi to text -2 thru -1 of ("0" & minutes of msgDate)
            
            -- Naming format: YYYY/MM/YYYYMMDD-HHMM_Sender_Subject_Mailbox_Random
            set charset to "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            set randSuffix to ""
            repeat 3 times
                set randSuffix to randSuffix & character (random number from 1 to 36) of charset
            end repeat
            return y & "/" & mo & "/" & y & mo & d & "-" & h & mi & "__" & msgSender & "__" & msgSubject 
        end makeSafeMailID

        -- === START ===
        my ensureFolderExists(exportFolderPath)
        set lastRunDate to my readTimestampFromFile(stateFilePath)
        set exportedCount to 0
        set latestDate to lastRunDate
        copy lastRunDate to endDate
        set year of endDate to (year of endDate as integer) + 1

        tell application "Mail"
            set theAccount to account accountName
            set allMailboxes to mailboxes of theAccount
            
            repeat with mbx in allMailboxes
                set mailboxName to name of mbx
                try
                    -- Filter messages after last run date (date sent covers sent mailboxes)
                    set newMessages to (messages of mbx whose (date received comes after lastRunDate or date sent comes after lastRunDate) and (date received comes before endDate or date sent comes before endDate))
                    
                    repeat with m in newMessages
                        try
                            set folder_name to my makeSafeMailID(mailboxName, m)
                            set folderPath to exportFolderPath & folder_name & "/"
                            set emlPath to folderPath & "message.eml"
                            
                            my ensureFolderExists(folderPath)
                            
                            -- Write EML file if it doesn't exist
                            set rawSource to source of m
                            set f to open for access (POSIX file emlPath) with write permission
                            set eof of f to 0
                            write rawSource to f
                            close access f
                            
                            set exportedCount to exportedCount + 1
                            
                            if date received of m > latestDate then
                                set latestDate to date received of m
                            end if
                        on error errMsg
                            log "Error saving mail: " & errMsg
                        end try
                    end repeat
                on error errMsg
                    log "Error reading mailbox " & mailboxName & ": " & errMsg
                end try
            end repeat
        end tell

        return "Exported " & exportedCount & " messages."
        '''

        p = Popen(['osascript', '-'], stdin=PIPE, stdout=PIPE, stderr=PIPE, universal_newlines=True)
        stdout, stderr = p.communicate(textwrap.dedent(script))
        print("APPLESCRIPT RESULTS")
        print(stdout, stderr)
        eml_files = WORKING_PATH.rglob('*.eml')
        if not eml_files and stderr.strip() != "":
            return f"{account}: ERROR running applescript\n{stderr.strip()}"
        
        result_files: list[tuple[datetime.datetime, Path]] = []
        timestamps = []
        try:
            to_ignore = [l.strip() for l in (OUTPUT_PATH  / "ignore.txt").read_text().splitlines()]
        except:
            to_ignore = []
        for eml_file in eml_files:
            if True in [ bad in eml_file.as_posix() for bad in to_ignore]:
                os.remove(eml_file)
                os.rmdir(eml_file.parent)
                continue

                
            with open(eml_file, "rb") as f:
                msg = BytesParser(policy=policy.default).parse(f)

            # extract metadata
            metadata = {
                "account_name": account,
                "eml_file": "message.eml",
            }
            email_headers = {v.lower(): v for v in [# Core / addressing / routing
                "From", "To", "Cc", "Bcc", "Reply-To", "Sender", "Return-Path", "Subject", 
                "Date", "Resent-Date", "Delivery-date",# Timing
                "Message-ID", "In-Reply-To", "References", "Thread-Topic", "Thread-Index", # Identification / threading
                "Received", "Delivered-To", "X-Forwarded-For", "X-Original-To", "X-Received", "SavedFromEmail", "Envelope-to", # Transport / routing trace            
                #"Authentication-Results", "DKIM-Signature", "DomainKey-Signature", "ARC-Seal", "ARC-Message-Signature", "ARC-Authentication-Results", "Received-SPF" # Authentication / anti-spoofing
                "User-Agent", "X-Mailer", "X-Originating-IP", "X-Source", # Client / sender info 
                "List-Id", "List-Unsubscribe", "List-Subscribe", # List / bulk mail
            ]}

            
            for target_key_lower in email_headers:
                # get_all returns a list of all headers matching this name (crucial for 'Received')
                header_values = msg.get_all(target_key_lower)
                if not header_values:
                    continue
                    
                cleaned_values_list = []
                
                for raw_value in header_values:
                    try:
                        # 1. Decode the header safely
                        decoded_value = str(make_header(decode_header(raw_value)))
                        
                        # 2. UNFOLD: Replace newlines followed by spaces/tabs with a single space
                        unfolded_value = re.sub(r'\r?\n[ \t]+', ' ', decoded_value)
                        # Remove any remaining raw newlines inside the text
                        unfolded_value = unfolded_value.replace('\n', ' ').replace('\r', ' ')
                        # Collapse multiple spaces into one
                        unfolded_value = " ".join(unfolded_value.split())
                        
                        if "date" in target_key_lower:
                            cleaned_values_list.append(parsedate_to_datetime(unfolded_value).isoformat())
                            
                        elif target_key_lower in ["received", "x-received", "return-path"]:
                            # Strip raw angle brackets around emails within the trace text
                            clean_trace = re.sub(r'[<>]', '', unfolded_value)
                            cleaned_values_list.append(clean_trace)
                            
                        elif target_key_lower in ["to", "cc", "bcc"]:
                            # Split comma-separated multiple recipients
                            recipients = re.split(r',\s*', unfolded_value)
                            for r in recipients:
                                if r.strip():
                                    name, email_str = parseaddr(r)
                                    cleaned_values_list.append(f"{name} ({email_str})" if name else email_str)
                                    
                        elif target_key_lower == "references":
                            # Extract all message IDs out of brackets
                            ids = re.findall(r'<([^>]+)>', unfolded_value)
                            cleaned_values_list.extend(ids if ids else [unfolded_value])
                            
                        elif target_key_lower in ["message-id", "in-reply-to", "envelope-to", "delivered-to", "from", "reply-to"]:
                            name, email_str = parseaddr(unfolded_value)
                            val = f"{name} ({email_str})" if name else email_str
                            # If parseaddr fails or isn't an email address, keep the stripped text
                            final_val = val if email_str else unfolded_value
                            cleaned_values_list.append(re.sub(r'[<>]', '', final_val))
                            
                        else:
                            cleaned_values_list.append(unfolded_value)
                            
                    except Exception as e:
                        cleaned_values_list.append(f"ERROR: Failed to decode, {e}")

                # 3. Assign to metadata dictionary
                if cleaned_values_list:
                    # Fields that should always be lists in YAML
                    list_fields = ["received", "x-received", "to", "cc", "bcc", "references"]
                    
                    if target_key_lower in list_fields:
                        if len(cleaned_values_list) == 1:
                            metadata[target_key_lower] = cleaned_values_list[0]
                        else:
                            metadata[target_key_lower] = " ; ".join(cleaned_values_list)
                    else:
                        # For single-value headers, just take the first/most recent one
                        metadata[target_key_lower] = cleaned_values_list[0]

            # Determine send/receive direction
            sender_addr = email.utils.parseaddr(msg.get("From", ""))[1].lower()
            to_addrs = []
            for key in ["to", "delivered-to", "envelope-to"]:
                to_addrs.extend([addr[1].lower() for addr in email.utils.getaddresses(msg.get_all(key,""))]) 
            
            account_alt = account.replace("@googlemail", "@gmail")
            if sender_addr == account or sender_addr == account_alt:
                metadata["direction"] = "sent"
            elif account in to_addrs or account_alt in to_addrs:
                metadata["direction"] = "received"
            else:
                metadata["direction"] = "unknown"
                print(f"Warning: Could not determine message direction for {eml_file}. From: {sender_addr}, To: {to_addrs}, Account: {account}")

            # Get received/send date
            email_date = None
            for key in "Date", "Delivery-date", "Resent-Date":
                if received_date := msg.get(key, None):
                    try:
                        email_date:datetime.datetime = parsedate_to_datetime(received_date)
                        timestamps.append(int(email_date.timestamp()))
                    except:
                        print("failed to parse date")

            # Create target dir. The AppleScript folder name (sender/subject
            # derived) may contain emoji/unicode — clean it so every path
            # this script creates is ASCII-safe for git and downstream tools.
            clean_folder = clean_filename(eml_file.parent.name, max_len=150)
            if email_date:
                target_base = OUTPUT_PATH / metadata["direction"] / str(email_date.year) / f"{email_date.month:02d}"
            else:
                target_base = OUTPUT_PATH / metadata["direction"] / "kein_datum"

            # Disambiguate: distinct mails can clean to the same folder name.
            # Identical bytes = re-export duplicate -> drop; otherwise suffix.
            new_eml_bytes = eml_file.read_bytes()
            target_path = target_base / clean_folder
            suffix_counter = 1
            while (target_path / "message.eml").exists():
                try:
                    if (target_path / "message.eml").read_bytes() == new_eml_bytes:
                        break  # same mail re-exported, keep existing files
                except OSError:
                    pass
                suffix_counter += 1
                target_path = target_base / f"{clean_folder}_{suffix_counter}"

            target_path.mkdir(parents=True, exist_ok=True) # Ensure parent directories exist

            target_file = target_path / "message.eml"
            target_file_md = target_path / "message.md"

            if target_file.exists():
                # Identical mail re-exported (timestamp overlap): nothing new.
                os.remove(eml_file)
                if not any(eml_file.parent.glob("*")):
                    eml_file.parent.rmdir()
                continue

            #Extract attachments
            attachment_names = set()
            for part in msg.walk():
                if part.is_multipart():
                    continue
                if filename := part.get_filename():
                    clean_name = clean_attachment_name(filename)
                    i=1
                    original_clean_name = clean_name
                    while clean_name in attachment_names or (target_path / "attachments" / clean_name).exists():
                        clean_name = f"{Path(original_clean_name).stem}_{i}{Path(original_clean_name).suffix}"
                        i += 1
                    attachment_names.add(clean_name)
                    attachment_path = target_path / "attachments"
                    attachment_path.mkdir(exist_ok=True, parents=True)
                    attachment_file = target_path / "attachments" / clean_name
                    attachment_file.write_bytes(part.get_payload(decode=True) or b"")
                    if "attachments" not in metadata:
                        metadata["attachments"] = []
                    metadata["attachments"].append(clean_name)

            # Extract message 
            message_text = ""
            message_html = ""
            for part in msg.walk():
                if part.is_multipart():
                    continue
                ctype = part.get_content_type()
                if part.get_filename():
                    continue
                try:
                    content = part.get_content()
                except:
                    continue
                if not content:
                    continue
                if ctype == "text/plain":
                    message_text += content
                elif ctype == "text/html":
                    message_html += content

            if message_text:
                message_text = re.sub(r'\n{3,}', '\n\n', message_text.strip())

            if message_html and not message_text:
                message_text = clean_html_email_to_markdown(message_html) # Using your cleaning pipeline

            elif message_text and message_html:
                # Check for standard "HTML placeholder" messages in the text part
                placeholders = ["view in browser", "enable html", "cannot read this email"]
                is_placeholder = any(p in message_text.lower() for p in placeholders)
                # If the text is just a placeholder, or suspiciously empty compared to HTML
                if is_placeholder or len(message_text) < 150 and len(message_html) > 2000:
                    message_text = clean_html_email_to_markdown(message_html)

            shutil.move(eml_file, target_file) # Move the entire temporary email folder to its permanent structured location
            yaml_string = yaml.dump(metadata, default_flow_style=False, allow_unicode=True)
            markdown_file_content = f"---\n{yaml_string}---\n\n{message_text}"
            target_file_md.write_text(markdown_file_content)
            result_files.append((email_date or datetime.datetime.fromtimestamp(0, tz=datetime.timezone.utc), target_file_md))

            if not any(eml_file.parent.glob("*")): # eml folder
                eml_file.parent.rmdir()
            if not  any(eml_file.parent.parent.glob("*")): # month folder
                eml_file.parent.parent.rmdir()
            if not  any(eml_file.parent.parent.parent.glob("*")):  # year folder
                eml_file.parent.parent.parent.rmdir()
            if not any(WORKING_PATH.glob("*")):
                WORKING_PATH.rmdir()

        _break = False
        if timestamps:
            timestamp = int(sorted(timestamps)[-1] - (2*3600))
            _break = True
        else:
            timestamp = int(float(stateFilePath.read_text()) + (180*24*60*60))

        if timestamp > datetime.datetime.now().timestamp():
            timestamp =  int(datetime.datetime.now().timestamp() -  (2*3600))
            _break = True
        stateFilePath.write_text(f"{timestamp}")
        if _break:
            break

    if git_autocommit and result_files:
        paths = [p.as_posix() for _, p in result_files]
        for i in range(0, len(paths), 10):
            batch = paths[i:i + 10]
            p = Popen(['git', 'add'] + batch, universal_newlines=True, cwd=OUTPUT_PATH)
            p.communicate()
        p = Popen(['git', 'commit', '-m', f"{len(result_files)} new raw files added"], universal_newlines=True, cwd=OUTPUT_PATH)
        p.communicate()
          
    return [p.as_posix() for _, p in sorted(result_files, key=lambda x: x[0])]


def clean_html_email_to_markdown(html_content):
    # 1. Parse HTML and remove code blocks
    soup = BeautifulSoup(html_content, 'html.parser')
    for element in soup(["script", "style", "head", "title", "meta"]):
        element.extract()
        
    # Remove hidden tracking pixels
    for img in soup.find_all('img'):
        try:
            if int(img.get('width')) < 10 or int(img.get('height')) < 10:
                img.extract()
        except:
            pass
    clean_html = str(soup)

    # 2. Configure converter for LLM compatibility
    converter = html2text.HTML2Text()
    converter.ignore_links = False      # Keep links if LLM needs to extract URLs
    converter.ignore_images = True     # Drop images to save tokens
    converter.body_width = 0           # Do not force-wrap text
    converter.protect_links = True     # Prevent links from breaking across lines
    markdown = converter.handle(clean_html)
    markdown = re.sub(r'\n{3,}', '\n\n', markdown)
    return markdown.strip()

def email_received(markdown_file: str) -> str:
    return markdown_file