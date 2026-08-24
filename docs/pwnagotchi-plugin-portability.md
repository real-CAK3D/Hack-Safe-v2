# Pwnagotchi Plugin Portability Notes

Source inspected: `/home/pi/src/pwnagotchi/pwnagotchi/plugins/default`.

Spac3-Gh0st keeps compatible behavior where it fits this Pi dashboard and avoids offensive/credential-upload defaults.

## auto-update.py
- Pwnagotchi purpose: This plugin checks when updates are available and applies them when internet is available.
- Callbacks: on_internet_available, on_loaded
- Signals/dependencies noticed: bettercap, internet, led, update, log
- Spac3-Gh0st portability: Partial / safe-only shim

## bt-tether.py
- Pwnagotchi purpose: This makes the display reachable over bluetooth
- Callbacks: on_loaded, on_ui_setup, on_ui_update, on_unload
- Signals/dependencies noticed: bluetooth, internet, led, update, log
- Spac3-Gh0st portability: Yes

## example.py
- Pwnagotchi purpose: An example plugin for pwnagotchi that implements all the available callbacks.
- Callbacks: on_ai_best_reward, on_ai_policy, on_ai_ready, on_ai_training_end, on_ai_training_start, on_ai_training_step, on_ai_worst_reward, on_association, on_bored, on_channel_hop, on_deauthentication, on_display_setup, on_epoch, on_excited, on_free_channel, on_handshake, on_internet_available, on_loaded, on_lonely, on_peer_detected, on_peer_lost, on_ready, on_rebooting, on_sad, on_sleep, on_ui_setup, on_ui_update, on_unfiltered_ap_list, on_unload, on_wait, on_webhook, on_wifi_update
- Signals/dependencies noticed: bettercap, handshake, deauth, webhook, internet, led, update, log
- Spac3-Gh0st portability: Partial / safe-only shim

## gpio_buttons.py
- Pwnagotchi purpose: GPIO Button support plugin
- Callbacks: on_loaded
- Signals/dependencies noticed: gpio, log
- Spac3-Gh0st portability: Yes / native Spac3-Gh0st version planned or added

## gps.py
- Pwnagotchi purpose: Save GPS coordinates whenever an handshake is captured.
- Callbacks: on_handshake, on_loaded, on_ready, on_ui_setup, on_ui_update, on_unload
- Signals/dependencies noticed: bettercap, handshake, gps, led, update, log
- Spac3-Gh0st portability: Yes / native Spac3-Gh0st version planned or added

## grid.py
- Pwnagotchi purpose: This plugin signals the unit cryptographic identity and list of pwned networks and list of pwned
- Callbacks: on_internet_available, on_loaded
- Signals/dependencies noticed: bettercap, handshake, internet, led, update, log
- Spac3-Gh0st portability: Partial / safe-only shim

## led.py
- Pwnagotchi purpose: This plugin blinks the PWR led with different patterns depending on the event.
- Callbacks: on_ai_best_reward, on_ai_ready, on_ai_training_start, on_ai_worst_reward, on_association, on_bored, on_deauthentication, on_epoch, on_excited, on_handshake, on_internet_available, on_loaded, on_lonely, on_peer_detected, on_peer_lost, on_ready, on_rebooting, on_sad, on_sleep, on_unread_inbox, on_updating, on_wait, on_wifi_update
- Signals/dependencies noticed: handshake, deauth, internet, led, update, log
- Spac3-Gh0st portability: Yes / native Spac3-Gh0st version planned or added

## logtail.py
- Pwnagotchi purpose: This plugin tails the logfile.
- Callbacks: on_config_changed, on_loaded, on_webhook
- Signals/dependencies noticed: webhook, led, log
- Spac3-Gh0st portability: Yes / native Spac3-Gh0st version planned or added

## memtemp.py
- Pwnagotchi purpose: A plugin that will display memory/cpu usage and temperature
- Callbacks: on_loaded, on_ui_setup, on_ui_update, on_unload
- Signals/dependencies noticed: led, update, log, memory, temperature
- Spac3-Gh0st portability: Yes / native Spac3-Gh0st version planned or added

## net-pos.py
- Pwnagotchi purpose: Saves a json file with the access points with more signal whenever a handshake is captured. When internet is available the files are converted in geo locations using Mozilla LocationService
- Callbacks: on_handshake, on_internet_available, on_loaded
- Signals/dependencies noticed: bettercap, handshake, internet, update, log
- Spac3-Gh0st portability: Partial / safe-only shim

## onlinehashcrack.py
- Pwnagotchi purpose: This plugin automatically uploads handshakes to https://onlinehashcrack.com
- Callbacks: on_internet_available, on_loaded, on_webhook
- Signals/dependencies noticed: bettercap, handshake, webhook, internet, led, update, log
- Spac3-Gh0st portability: Partial / safe-only shim

## paw-gps.py
- Pwnagotchi purpose: Saves GPS coordinates whenever an handshake is captured. The GPS data is get from PAW on android.
- Callbacks: on_handshake, on_loaded
- Signals/dependencies noticed: handshake, gps, bluetooth, log
- Spac3-Gh0st portability: Partial / safe-only shim

## session-stats.py
- Pwnagotchi purpose: This plugin displays stats of the current session.
- Callbacks: on_epoch, on_loaded, on_webhook
- Signals/dependencies noticed: handshake, deauth, webhook, led, update, log, temperature
- Spac3-Gh0st portability: Yes / native Spac3-Gh0st version planned or added

## switcher.py
- Pwnagotchi purpose: This plugin is a generic task scheduler.
- Callbacks: on_loaded
- Signals/dependencies noticed: bettercap, handshake, deauth, webhook, internet, led, update, log
- Spac3-Gh0st portability: Partial / safe-only shim

## ups_lite.py
- Pwnagotchi purpose: A plugin that will add a voltage indicator for the UPS Lite v1.1
- Callbacks: on_loaded, on_ui_setup, on_ui_update, on_unload
- Signals/dependencies noticed: led, gpio, update, log
- Spac3-Gh0st portability: Yes

## watchdog.py
- Pwnagotchi purpose: Restart pwnagotchi when blindbug is detected.
- Callbacks: on_epoch, on_loaded
- Signals/dependencies noticed: led, update, log
- Spac3-Gh0st portability: Yes / native Spac3-Gh0st version planned or added

## webcfg.py
- Pwnagotchi purpose: This plugin allows the user to make runtime changes.
- Callbacks: on_config_changed, on_internet_available, on_loaded, on_ready, on_webhook
- Signals/dependencies noticed: webhook, internet, led, update, log
- Spac3-Gh0st portability: Yes / native Spac3-Gh0st version planned or added

## webgpsmap.py
- Pwnagotchi purpose: a plugin for pwnagotchi that shows a openstreetmap with positions of ap-handshakes in your webbrowser
- Callbacks: on_config_changed, on_loaded, on_webhook
- Signals/dependencies noticed: bettercap, handshake, gps, webhook, update, log
- Spac3-Gh0st portability: Yes / native Spac3-Gh0st version planned or added

## wigle.py
- Pwnagotchi purpose: This plugin automatically uploads collected wifis to wigle.net
- Callbacks: on_internet_available, on_loaded
- Signals/dependencies noticed: bettercap, handshake, gps, internet, led, update, log, wigle
- Spac3-Gh0st portability: Partial / safe-only shim

## wpa-sec.py
- Pwnagotchi purpose: This plugin automatically uploads handshakes to https://wpa-sec.stanev.org
- Callbacks: on_internet_available, on_loaded, on_webhook
- Signals/dependencies noticed: bettercap, handshake, webhook, internet, led, update, log, wpa-sec
- Spac3-Gh0st portability: Partial / safe-only shim
