from machine import ADC, Pin
import time
import network
import urequests
import utime
import secrets


# --- Wi-Fi Data ---
SSID = secrets.SSID
PASSWORD = secrets.PASSWORD

# --- Telegram Data ---
TELEGRAM_BOT_TOKEN = secrets.TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID = secrets.TELEGRAM_CHAT_ID

# --- Pins Setup ---
ldr = ADC(0)  # GP26
led = Pin(0, Pin.OUT)
buzzer = Pin(16, Pin.OUT)
button = Pin(17, Pin.IN, Pin.PULL_UP)

# --- States ---
fridge_open = False           # Tracks if fridge is currently open
open_start_time = None        # Timestamp when fridge was opened
alert_sent = False            # Tracks if Telegram alert was sent
monitoring = False            # Indicates whether monitoring is active
last_beep_time = 0            # For periodic beeping of buzzer
fridge_warning_sent = False   # True if fridge open warning has already been sent
was_paused = True             # Used to detect state change from active to paused
toggle_message = None         # Stores message to send when toggling state
last_press_time = 0           # For button debounce timing

THRESHOLD = 500               # LDR threshold (if < 500 fridge is open)


# --- Wi-Fi Connect ---
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    print("Connecting to Wi-Fi...", end="")
    while not wlan.isconnected():
        print(".", end="")
        time.sleep(1)
    print("\nConnected, IP:", wlan.ifconfig()[0])
    send_telegram("CoolKeeper connected to Wi-Fi")


# --- Send Telegram Message ---
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {'chat_id': TELEGRAM_CHAT_ID, 'text': message}
    try:
        r = urequests.post(url, json=data)
        r.close()
        del r
    except Exception as e:
        print("Telegram send error:", e)


# --- Button Interrupt Handler ---
def button_pressed(pin):
    global monitoring, fridge_open, open_start_time, alert_sent
    global was_paused, toggle_message, last_press_time

    current_time = utime.ticks_ms()
    if utime.ticks_diff(current_time, last_press_time) > 300:
        last_press_time = current_time
        monitoring = not monitoring
        if monitoring:
            toggle_message = "Monitoring started. Press the button to pause"
            was_paused = False
        else:
            toggle_message = "Monitoring paused. Press the button to resume"
            # Reset states when paused
            fridge_open = False
            open_start_time = None
            alert_sent = False
            led.off()
            buzzer.off()


# --- Setup Button Interrupt ---
button.irq(trigger=Pin.IRQ_FALLING, handler=button_pressed)

# --- Main Program ---
connect_wifi()
send_telegram("Press the button to start monitoring")

while True:
    # If user toggled button
    if toggle_message:
        print(toggle_message)
        send_telegram(toggle_message)
        toggle_message = None

    if monitoring:
        light_level = ldr.read_u16() // 64
        print("Light level:", light_level)
        current_time = time.time()

        # --- Fridge is open ---
        if light_level <= THRESHOLD:
            # First time detecting fridge open
            if not fridge_open:
                print("Fridge OPEN")
                open_start_time = current_time
                fridge_open = True
                alert_sent = False
                last_beep_time = 0
                led.on()

            # Check if fridge has been open too long
            elif open_start_time is not None and current_time - open_start_time >= 20:
                # Send warning once
                if not alert_sent:
                    send_telegram("Warning: Fridge open more than 20 seconds!")
                    alert_sent = True
                    fridge_warning_sent = True
                    last_beep_time = current_time

                # Buzzer beeps every second until fridge is closed
                if current_time - last_beep_time >= 1:
                    buzzer.on()
                    time.sleep(0.1)
                    buzzer.off()
                    last_beep_time = current_time

        # --- Fridge is closed again ---
        else:
            if fridge_open:
                print("Fridge CLOSED")
                fridge_open = False
                open_start_time = None
                alert_sent = False
                led.off()
                buzzer.off()
                # Notify closure only if a warning was previously sent
                if fridge_warning_sent:
                    send_telegram("Fridge has been closed")
                    fridge_warning_sent = False
    else:
        # Show paused state by blinking LED
        led.toggle()
        time.sleep(0.5)
        if not was_paused:
            was_paused = True

    # loop delay
    time.sleep(1)
