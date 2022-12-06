# home-assistant-hypervolt-charger
A [Home Assistant](https://www.home-assistant.io/) Custom Component integration for the [Hypervolt electric vehicle (EV) charger](https://hypervolt.co.uk/). This integration replicates functionality of the Hypervolt mobile app and allows actions to be automated and data to be logged within Home Assistant.

* Start or stop charging based on the cheapest half hour slots available within your agile electricity tariff
* Automatically manage charging when excess solar is available and your home storage battery is full
* Ensure that your charger is configured for the night's charge, every night, no matter what settings were changed during the day e.g. Scheduled Charge mode on, max current set, Boost mode set, ready to charge
* Stop charging when a specific amount of energy has been supplied, or specific state of charge is reached
* ...

![](demo.gif)

# Installation

Copy contents of custom_components folder to your home-assistant config/custom_components folder or install through HACS. After reboot of Home-Assistant, this integration can be configured through the integration setup UI.

