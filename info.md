# home-assistant-hypervolt-charger

A Home Assistant Custom Component integration for the Hypervolt electric vehicle (EV) charger. This integration replicates functionality of the Hypervolt mobile app and allows actions to be automated and data to be logged within Home Assistant.

- Start or stop charging based on the cheapest half hour slots available within your agile electricity tariff
- Automatically manage charging when excess solar is available and your home storage battery is full (Super Eco mode alone may not work as you'd like when a home battery is installed)
- Ensure that your charger is configured for the night's charge, every night, no matter what settings were changed during the day e.g. Scheduled Charge mode on, max current set, Boost mode set, ready to charge
- Stop charging when a specific amount of energy has been supplied, or specific state of charge is reached (assuming the EV's state of charge is available via some other integration)
- ...

# Use

Once installed within Home Assistant, and having restarted Home Assistant, you should be able to add the Hypervolt Charger integration. You'll be asked for your Hypervolt account credentials then the integration should find your charger and create a Device with the name of your charger's serial number. The various entities can then be added to dashboards, automations etc. as you wish.

<img src="https://github.com/gndean/home-assistant-hypervolt-charger/blob/main/demo.gif?raw=true" alt="Demo">
