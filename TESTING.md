# Verification guide

Use only data and devices you own or are authorized to examine. Work with a
throwaway test conversation; deleted records can be overwritten at any time and
cannot be guaranteed recoverable.

## 1. Start the application

Run `run_app.bat`, open `http://localhost:5173`, and create a new case called
something like `WhatsApp deletion test`.

## 2. Check the encrypted-backup path

1. Import a WhatsApp local backup ending in `.crypt14`.
2. The evidence table must identify it as **WhatsApp**, show **SQLite: no**, and
   display **Provide key & decrypt**. This is the expected result: ciphertext
   is not message evidence.
3. Select that action and provide the matching, authorized key file. The key is
   used for the request only; it is not retained by the application.
4. On success, a new evidence item ending in `.decrypted.db` appears. It must
   show **SQLite: yes** before messages or deleted-data recovery are trusted.
5. If the key is wrong or belongs to another backup, decryption fails with a
   verification error and no decrypted evidence item is created.

The app does not obtain keys from phones, accounts, or protected device
storage. On older Android installations, the key is commonly located in the
app-private path `/data/data/com.whatsapp/files/key`; it is not visible to a
normal file browser and accessing it generally requires authorized device
access (often a forensic/rooted acquisition). Obtain and export it only
through the device owner or an authorized forensic workflow.

## 3. Test a real deletion without risking important data

1. In a test chat, send a uniquely identifiable message such as
   `MAR delete test 2026-09-21 12345`.
2. Close WhatsApp before collecting files so its database and companion files
   are not changing. Retain a read-only copy of the pre-deletion database and,
   if present, its `-wal` companion.
3. Delete the test message in WhatsApp, close it again, then collect a separate
   post-deletion copy. Import the post-deletion SQLite database (or scan the
   local PC) into a new case.
4. Wait for the analysis card to finish. Check **Conversations**, **Search**,
   and the special `[RECOVERED DELETED]` conversation for the unique text.
5. A found fragment is marked `DELETED_RECOVERED` and includes its recovery
   method and confidence. Export the audit report if you need to preserve the
   result.

## Interpreting results

* **Encrypted / needs key**: recovery has not been attempted; decrypt first.
* **0 recovered records after decryption**: this is a valid outcome, not an
  application error. SQLite may have reused or securely erased the space, or
  WhatsApp/Desktop storage may not retain a recoverable copy.
* **Recovered text**: treat it as a fragment unless it can be corroborated by
  timestamp, conversation metadata, WAL data, or another acquisition.

## Telegram Desktop export test

Telegram Desktop can create a readable, official export that this app imports
directly. Use a disposable cloud chat (not a secret chat), send a unique
message such as `TG export test 2026-09-21 12345`, then use **Settings →
Advanced → Export Telegram data** or **Export chat history** from that chat.
Choose **Machine-readable JSON**, export, and upload the resulting `result.json`
file into a case. The analysis should show Telegram conversations and the test
message as `ACTIVE` evidence. Telegram exports do not contain messages deleted
before export, so this verifies truthful message parsing rather than deleted
record recovery.
