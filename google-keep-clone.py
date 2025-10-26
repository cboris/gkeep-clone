import gkeepapi
import keyring
import time 


# === HELPER FUNCTION: NOTE COUNTER ===
def count_source_notes(keep_instance):
    """
    Counts total and archived notes in a gkeepapi.Keep instance.
    The Keep instance must have already been authenticated and synced.
    
    Returns: A tuple (total_notes, archived_notes, active_notes)
    """
    total_notes = 0
    archived_notes = 0

    # Iterate over all non-trashed notes in the source account
    for note in keep_instance.all():
        # gkeepapi.all() generally excludes trashed notes, but we confirm
        if not note.trashed:
            total_notes += 1
            
            # Check if the note is archived
            if note.archived:
                archived_notes += 1

    active_notes = total_notes - archived_notes
    return total_notes, archived_notes, active_notes

# === LOGIN ===
def login2accounts(src_email,dest_email):
    
    print("Logging into source (enterprise)...")
    tokensrc = keyring.get_password('google-keep-token', src_email)

    src = gkeepapi.Keep()
    src.authenticate(src_email,tokensrc)




    print("Logging into destination (personal)...")
    dst = gkeepapi.Keep()
    tokendst = keyring.get_password('google-keep-token', dest_email)
    dst.authenticate(dest_email, tokendst)

    return src,dst


def copy_notes(src,dst,dst_labels):
    # === COPY NOTES ===
    copied = 0
    for note in src.all():
        # Skip trashed notes
        if note.trashed:
            continue

        # Attempt to copy the note with retries
        for attempt in range(MAX_RETRIES):
            try:
                # Skip duplicates by title+text
                if any(n.title == note.title and n.text == note.text for n in dst.all()):
                    continue

                # Create new note
                new_note = dst.createNote(note.title, note.text)
                new_note.pinned = note.pinned
                new_note.archived = note.archived
                new_note.color = note.color

                # Copy labels
                for lbl in note.labels.all():
                    if lbl.name in dst_labels:
                        new_note.labels.add(dst_labels[lbl.name])

                # Copy attachments (images)
                if hasattr(note, 'media'):
                    for att in note.media:
                        try:
                            blob = att.blob
                            new_note.addImage(blob)
                        except Exception as e:
                            print(f"⚠️ Failed to copy attachment from note '{note.title}': {e}")

                copied += 1
                break
            except Exception as e:
                # Catch any unexpected errors, especially potential API/network errors
                if attempt < MAX_RETRIES - 1:
                    # Exponentially increase wait time
                    wait_time = DELAY_SECONDS * (2 ** attempt) 
                    print(f"\n⚠️ Encountered error: {e}. Retrying note '{note.title}' in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"\n❌ Failed to copy note '{note.title}' after {MAX_RETRIES} attempts. Skipping.")
                    # Force a sync to ensure everything else is saved
                    dst.sync()
                    break # Move to the next note


    time.sleep(DELAY_SECONDS) # Safety measute to avoid rate limiting and locking account
    if copied % 20 == 0:
        print(f"Copied {copied} notes so far...")
        dst.sync()
    return copied

def copy_reminders(src,dst):
    # === PREPARE DESTINATION NOTES FOR LOOKUP ===
    # Create a faster lookup structure for destination notes: (title, text) -> dst_note
    dst_notes_lookup = {}
    for note in dst.all():
        # Only map non-trashed notes
        if not note.trashed:
            dst_notes_lookup[(note.title, note.text)] = note

    # === COPY REMINDERS ===
    print("\nStarting Reminder Copy Pass...")
    reminders_copied_count = 0
    total_source_notes_with_reminders = 0

    for src_note in src.all():
        # Skip trashed notes
        if src_note.trashed:
            continue

        # 1. Check if source note has reminders
        if hasattr(note, 'reminders'):
            if not src_note.reminders:
                continue
        
        total_source_notes_with_reminders += 1
        
        # 2. Match source note to destination note using (title, text)
        lookup_key = (src_note.title, src_note.text)
        if lookup_key not in dst_notes_lookup:
            print(f"  ⚠️ Warning: Could not find destination note matching source: '{src_note.title}'. Skipping reminder.")
            continue

        dst_note = dst_notes_lookup[lookup_key]

        # 2. CRITICAL STEP: Fetch a fresh, complete, and mutable copy of the destination note
        try:
            dst_note = dst.get(dst_note) 
        except Exception as e:
            print(f"  ❌ Error fetching fresh destination note ID {dst_note}: {e}. Skipping.")
            continue

        # 3. Apply Reminders (with retry logic for safety)
        for attempt in range(MAX_RETRIES):
            try:
                # Get the raw reminder objects from the source
                src_reminders_list = src_note.reminders.all() 
                
                # Use the .set() method on the destination note's reminder object
                dst_note.reminders.set(src_reminders_list)
                
                reminders_copied_count += 1
                print(f"  ✓ Copied {len(src_reminders_list)} reminder(s) to note: '{dst_note.title}'")
                break # Success, move to the next source note

            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    wait_time = DELAY_SECONDS * (2 ** attempt) 
                    print(f"  ⚠️ Error: {e}. Retrying reminder for '{dst_note.title}' in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"  ❌ Failed to copy reminders for '{dst_note.title}' after {MAX_RETRIES} attempts. Skipping.")
                    break # Move to the next source note

        # Introduce a delay to respect Google's potential rate limits on writes
        time.sleep(DELAY_SECONDS) 

    # Final sync to save all the updated reminders
    dst.sync()

    print("\n==========================================================")
    print(f"✅ Reminder Copy Complete.")
    print(f"Notes with Reminders in Source: {total_source_notes_with_reminders}")
    print(f"Notes successfully updated with Reminders: {reminders_copied_count}")
    print("==========================================================")


def sync_labels(src,dst):
    # === SYNC LABELS ===
    dst_labels = {lbl.name: lbl for lbl in dst.labels()}
    for lbl in src.labels():
        if lbl.name not in dst_labels:
            new_lbl = dst.createLabel(lbl.name)
            dst_labels[lbl.name] = new_lbl
    return dst_labels


# === CONFIG ===
SRC_EMAIL = "source_email"


DST_EMAIL = "dest_email"


DELAY_SECONDS = 2  # Recommended safe delay
MAX_RETRIES = 3

# === MAIN ======

src,dst = login2accounts(SRC_EMAIL,DST_EMAIL)

print("Syncing source...")
src.sync()
dst.sync()

copied = 0

# === USE THE FUNCTION AND PRINT COUNTS ===
total_notes, archived_notes, active_notes = count_source_notes(src)

print(f"\nSource Account Note Count:")
print(f"  Total Notes (excluding trash): {total_notes}")
print(f"  Archived Notes: {archived_notes}")
print(f"  Active Notes: {active_notes}")


dst_labels = sync_labels(src,dst)
copied = copy_notes(src,dst,dst_labels)

copy_reminders(src,dst)
        



# Final sync
dst.sync()

print(f"✅ Done. Copied {copied} notes successfully (including archived + images).")
