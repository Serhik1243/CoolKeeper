from machine import ADC, Pin
import time
import network
import urequests

# --- Wi-Fi data ---
SSID = "Tele2_20d5e9"
PASSWORD = "zzmyadnh"

# --- Telegram data ---
TELEGRAM_BOT_TOKEN = '7585941863:AAEKEouVoGDlCCtTjbRFSaIi4S0AyULRCJA'
TELEGRAM_CHAT_ID = 648876888

# --- Pins ---
# LDR sensor GP26
ldr = ADC(0)
# LED indicator
led = Pin(0, Pin.OUT)
# Buzzer
buzzer = Pin(16, Pin.OUT)
# Button GP17
button = Pin(17, Pin.IN, Pin.PULL_UP)

# --- Thresholds and states ---
fridge_open = False
open_start_time = None
alert_sent = False
# Start paused
monitoring = False
last_beep_time = 0
# light_level less or equal 500 - fridge open
THRESHOLD = 500


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
    send_telegram("CoolKeeper connected to Wi-Fi.")


# --- Telegram send ---
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {'chat_id': TELEGRAM_CHAT_ID, 'text': message}
    print("Sending:", data)
    try:
        r = urequests.post(url, json=data)
        print("Response:", r.text)
    except Exception as e:
        print("Telegram send error:", e)


# --- Button interrupt handler ---
def button_pressed(pin):
    global monitoring, fridge_open, open_start_time, alert_sent
    monitoring = not monitoring
    print("Monitoring toggled to", monitoring)
    if not monitoring:
        # Reset states and turn off outputs when paused
        fridge_open = False
        open_start_time = None
        alert_sent = False
        led.off()
        buzzer.off()
        send_telegram("CoolKeeper monitoring paused.")
    else:
        send_telegram("CoolKeeper monitoring started.")


# Attach interrupt to button
button.irq(trigger=Pin.IRQ_FALLING, handler=button_pressed)

# --- Main ---
connect_wifi()
print("CoolKeeper ready. Press the button to start/pause monitoring.")

while True:
    if monitoring:
        # Scale to 0–1023
        light_level = ldr.read_u16() // 64  
        print("Light level:", light_level)
        current_time = time.time()

        if light_level <= THRESHOLD:
            if not fridge_open:
                print("Fridge OPEN")
                open_start_time = current_time
                fridge_open = True
                alert_sent = False
                last_beep_time = 0
                led.on()
            elif open_start_time is not None and current_time - open_start_time >= 5:
                if not alert_sent:
                    send_telegram("CoolKeeper Warning: Fridge open more than 5 seconds!")
                    alert_sent = True
                    last_beep_time = current_time

                if current_time - last_beep_time >= 1:
                    buzzer.on()
                    time.sleep(0.1)
                    buzzer.off()
                    last_beep_time = current_time
        else:
            if fridge_open:
                print("Fridge CLOSED")
                fridge_open = False
                open_start_time = None
                alert_sent = False
                led.off()
                buzzer.off()
    else:
        print("Monitoring paused. Press button to start.")

    time.sleep(1)
