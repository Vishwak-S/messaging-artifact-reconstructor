import sqlite3
import os
import time

def create_whatsapp_db():
    os.makedirs("whatsapp", exist_ok=True)
    conn = sqlite3.connect("whatsapp/msgstore.db")
    c = conn.cursor()
    c.execute("CREATE TABLE message (_id INTEGER PRIMARY KEY, key_remote_jid TEXT, sender_jid_row_id TEXT, data TEXT, timestamp INTEGER, message_type INTEGER, status INTEGER)")
    c.execute("CREATE TABLE chat (_id INTEGER PRIMARY KEY, jid_row_id TEXT, subject TEXT, display_name TEXT)")
    c.execute("CREATE TABLE jid (_id INTEGER PRIMARY KEY, user TEXT, display_name TEXT)")
    
    c.execute("INSERT INTO jid (user, display_name) VALUES ('+1234567890', 'Alice')")
    c.execute("INSERT INTO jid (user, display_name) VALUES ('+0987654321', 'Bob')")
    
    c.execute("INSERT INTO chat (jid_row_id, subject, display_name) VALUES ('+1234567890', '', 'Alice Chat')")
    
    now = int(time.time() * 1000)
    c.execute("INSERT INTO message (key_remote_jid, sender_jid_row_id, data, timestamp, message_type, status) VALUES ('+1234567890', '+1234567890', 'Hello from Alice', ?, 0, 1)", (now - 10000,))
    c.execute("INSERT INTO message (key_remote_jid, sender_jid_row_id, data, timestamp, message_type, status) VALUES ('+1234567890', 'me', 'Hi Alice!', ?, 0, 1)", (now,))
    
    conn.commit()
    conn.close()

def create_telegram_db():
    os.makedirs("telegram", exist_ok=True)
    conn = sqlite3.connect("telegram/cache4.db")
    c = conn.cursor()
    c.execute("CREATE TABLE messages (mid INTEGER PRIMARY KEY, uid INTEGER, did INTEGER, date INTEGER, message TEXT, type INTEGER, out INTEGER)")
    c.execute("CREATE TABLE users (uid INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT, username TEXT)")
    c.execute("CREATE TABLE dialogs (did INTEGER PRIMARY KEY, date INTEGER)")
    
    c.execute("INSERT INTO users (uid, first_name, last_name, username) VALUES (1, 'Charlie', 'Day', 'charlie')")
    c.execute("INSERT INTO dialogs (did, date) VALUES (1, ?)", (int(time.time()),))
    
    now = int(time.time())
    c.execute("INSERT INTO messages (uid, did, date, message, type, out) VALUES (1, 1, ?, 'Telegram msg 1', 0, 0)", (now - 100,))
    c.execute("INSERT INTO messages (uid, did, date, message, type, out) VALUES (2, 1, ?, 'Reply on TG', 0, 1)", (now,))
    
    conn.commit()
    conn.close()

def create_signal_db():
    os.makedirs("signal", exist_ok=True)
    conn = sqlite3.connect("signal/signal.db")
    c = conn.cursor()
    c.execute("CREATE TABLE sms (_id INTEGER PRIMARY KEY, thread_id INTEGER, address TEXT, date INTEGER, date_sent INTEGER, body TEXT, read INTEGER, type INTEGER)")
    c.execute("CREATE TABLE thread (_id INTEGER PRIMARY KEY, date INTEGER, recipient_id INTEGER)")
    c.execute("CREATE TABLE recipient (_id INTEGER PRIMARY KEY, phone TEXT, system_display_name TEXT)")
    
    c.execute("INSERT INTO recipient (phone, system_display_name) VALUES ('+11111111', 'Dave')")
    c.execute("INSERT INTO thread (recipient_id, date) VALUES (1, ?)", (int(time.time()),))
    
    now = int(time.time() * 1000)
    c.execute("INSERT INTO sms (thread_id, address, date, date_sent, body, read, type) VALUES (1, '+11111111', ?, ?, 'Signal test', 1, 87)", (now, now))
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    create_whatsapp_db()
    create_telegram_db()
    create_signal_db()
    print("Synthetic databases created.")
