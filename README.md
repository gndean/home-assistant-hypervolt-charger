![](https://img.shields.io/github/v/release/gndean/home-assistant-hypervolt-charger?include_prereleases)

# home-assistant-hypervolt-charger

A [Home Assistant](https://www.home-assistant.io/) Custom Component integration for the [Hypervolt electric vehicle (EV) charger](https://hypervolt.co.uk/). This integration replicates functionality of the Hypervolt mobile app and allows actions to be automated and data to be logged within Home Assistant.

- Start or stop charging based on the cheapest half hour slots available within your agile electricity tariff
- Automatically manage charging when excess solar is available and your home storage battery is full (Super Eco mode alone may not work as you'd like when a home battery is installed)
- Ensure that your charger is configured for the night's charge, every night, no matter what settings were changed during the day e.g. Scheduled Charge mode on, max current set, Boost mode set, ready to charge
- Stop charging when a specific amount of energy has been supplied, or specific state of charge is reached (assuming the EV's state of charge is available via some other integration)
- ...

![](demo.gif)

# Installation

Copy contents of custom_components folder to your home-assistant config/custom_components folder or install through [HACS](https://hacs.xyz/). After reboot of Home-Assistant, this integration can be configured through the integration setup UI.

# Use

Once installed within Home Assistant, and having restarted Home Assistant, you should be able to add the Hypervolt Charger integration. You'll be asked for your Hypervolt account credentials then the integration should find your charger and create a Device with the name of your charger's serial number. The various entities can then be added to dashboards, automations etc. as you wish.

# Synchronisation model

The integration uses the hypervolt.co.uk APIs so is dependent on the cloud. Most of the settings are updated via websocket pushes so changes are reflected to/from the integration near immediately. An exception is the Activation Mode. For this, and as a fallback in case a push message is missed, the integration also polls the Hypervolt APIs every 5 minutes to refresh the state.

# Entities

The integration is intended to match the features of the iOS and Android apps. I've tried to keep the naming similar where possible. The entities exposed are:

## ??????? Hypervolt Charging (Switch)

This allows the current charging state to be read and set. It matches the big Charging switch in the app.

?????? There is also the `Hypervolt Charging Readiness` sensor that gives slightly more information about the charge state.

## ??????? Hypervolt Lock State (Switch)

Matches the lock feature in the app and allows locking of the charger. The `Lock Pending` state is mapped to `On`

## ???? Hypervolt Activation Mode (Select)

Switches between 
* `Plug and Charge` and 
* `Schedule Charge` 

modes.

?????? Changes to this setting are not reflected in realtime within the integration or Hypervolt app. If changed externally to the integration its state should update to the correct state within 5 minutes.

?????? Currently, the schedule itself cannot be changed - see Known Limitations

## ???? Hypervolt Charge Mode (Select)

Switches between `Boost`, `Eco` and `Super Eco` modes.

## ???? Hypervolt Max Current (Number)

Reads and sets the maximum charging current, in Amps.

## ???? Hypervolt LED Brightness (Number)

Reads and sets the LED brightness, in percent, as available via Settings within the app

?????? The LED Mode isn't currently supported by the integration

## ???? Hypervolt Charging Readiness (Sensor)

One of: 
* `Charging`
* `Ready`
* `Not Ready - Force Stopped`

?????? `Not Ready - Force Stopped` was added to overcome a gotcha with Hypervolt. If the user manually stops a charge by switching charging off via the app or integration, the Hypervolt charger remembers this state and if later is switched into Schedule Charge activation mode, the scheduled charge _will not automatically start_ as might be expected. To overcome this, the Charging switch needs to be manually toggled. This can be done when in Scheduled mode even outside of the schedule window and will switch the `Hypervolt Charging Readiness` state back to `Ready`. ?????? In the Hypervolt app, there doesn't appear to be a way of telling whether the charger is ready or not.

## ???? Hypervolt Voltage, Hypervolt Charger Current (Sensors)

_Only available during a charging session_, these represent the voltage and current from the Hypervolt charger.

?????? This integration just reports the values from the Hypervolt APIs. No assurance of accuracy of the values is given!

## ???? Hypervolt CT Current, Hypervolt CT Power (Sensors) 

_Only available during a charging session_, these represent the current and power seen by the external CT clamp so will typically measure the household, or at least, whole circuit load, not just the Hypervolt.

?????? This integration just reports the values from the Hypervolt APIs. No assurance of accuracy of the values is given!

## ???? Hypervolt Session Carbon Saved, Hypervolt Session ID, Hypervolt Session Energy (Sensors)

Are fields related to the current, or most recent charging session.

?????? `Hypervolt Session Energy` just reports the session energy exactly from the Hypervolt APIs and resets for each new session. The value may be noisy i.e. decrease slightly during the charging session and will reset each charging session. For this reason, it is not a good choice to use for energy measurement within Home Assistant. For that, use `Hypervolt Session Energy Total Increasing` instead.

## ?????? Hypervolt Session Energy Total Increasing (Sensor)

This is a sensor of state class [total_increasing](https://developers.home-assistant.io/blog/2021/08/16/state_class_total/) which means that it is suitable for energy measurement within Home Assistant. Unlike `Hypervolt Session Energy`, the value is not taken directly from the Hypervolt APIs, cannot decrease during a session and will only reset on a new charging session, for which the [total_increasing](https://developers.home-assistant.io/blog/2021/08/16/state_class_total/) logic will handle. For a discussion of why this sensor was created, see [Sensor provides negative value when reset (HA Energy Dashboard) #5](https://github.com/gndean/home-assistant-hypervolt-charger/issues/5)

## ~~???? Hypervolt Session Money Spent~~ 

Sensor removed as it was based on the fixed 14p / unit tariff calculations so never correct.

# Known limitations

- Only tested with a Hypervolt Home 2.0 charge point
- Only one charger per account supported. If you have more than one, only the first will be found
- Log in has to be via via email address and password. Google or Apple login not supported
- The charger name is not supported. The Device name in Home Assistant will be your charger's serial
- English language only
- Schedule _times_ cannot be read or set, only the Schedule _mode_ can be changed. I think we probably need [this](https://github.com/home-assistant/core/pull/81943) feature within Home Assistant, to allow integrations to use DateTime fields, before controlling the schedule is feasible. Unless you know better? ????\
  ?????? You can of course now use Home Assistant to control starting and stopping your charger instead of relying on the Hypervolt schedule
- LED modes are not supported
- Money spent calculations not supported. In December 2022, Hypervolt added  tariff-aware calculations within the app. I will see if we can support this in a future release.