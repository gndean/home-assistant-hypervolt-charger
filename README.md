![](https://img.shields.io/github/v/release/gndean/home-assistant-hypervolt-charger?include_prereleases)

# home-assistant-hypervolt-charger

A [Home Assistant](https://www.home-assistant.io/) Custom Component integration for the [Hypervolt electric vehicle (EV) charger](https://hypervolt.co.uk/). This integration replicates functionality of the Hypervolt mobile app and allows actions to be automated and data to be logged within Home Assistant.

- Start or stop charging based on the cheapest half hour slots available within your agile electricity tariff
- Automatically manage charging when excess solar is available and your home storage battery is full (Super Eco mode alone may not work as you'd like when a home battery is installed)
- Ensure that your charger is configured for the night's charge, every night, no matter what settings were changed during the day e.g. Scheduled Charge mode on, max current set, Boost mode set, ready to charge
- Stop charging when a specific amount of energy has been supplied, or specific state of charge is reached (assuming the EV's state of charge is available via some other integration)
- ...

![](demo.gif)

# Current State

⚠️ Consider the current state of the integration a beta. If the installation instructions don't make sense to you or you've not installed custom Home Assistant integrations before, this probably isn't for you yet. The integration likely has serious bugs too due to very limited testing. I hope all this will improve over time.

# Installation

Copy contents of custom_components folder to your home-assistant config/custom_components folder or install through HACS. After reboot of Home-Assistant, this integration can be configured through the integration setup UI.

# Use

Once installed within Home Assistant, and having restarted Home Assistant, you should be able to add the Hypervolt Charger integration. You'll be asked for your Hypervolt account credentials then the integration should find your charger and create a Device with the name of your charger's serial number. The various entities can then be added to dashboards, automations etc. as you wish.

# Synchronisation model

The integration uses the hypervolt.co.uk APIs so is dependent on the cloud. Most of the settings are updated via websocket pushes so changes are reflected to/from the integration near immediately. An exception is the Activation Mode. For this, and as a fallback in case a push message is missed, the integration also polls the Hypervolt APIs every 5 minutes to refresh the state.

# Features

The integration is intended to match the features of the iOS and Android apps. I've tried to keep the naming similar where possible. The entities exposed are:

- `Hypervolt Charging` (Switch). This allows the current charging state to be read and set. It matches the big Charging switch in the app. \
  ℹ️ There is also the `Hypervolt Charging Readiness` sensor that gives slightly more information about the charge state.
- `Hypervolt Lock State` (Switch). Matches the lock feature in the app and allows locking of the charger. The `Lock Pending` state is mapped of `On`
- `Hypervolt Activation Mode` (Select). Switches between `Plug and Charge` and `Schedule Charge` modes.\
  ℹ️ Changes to this setting are not reflected in realtime within the integration or Hypervolt app. If changed externally to the integration its state should update to the correct state within 5 minutes.\
  ℹ️ Currently, the schedule itself cannot be changed - see Known Limitations
- `Hypervolt Charge Mode` (Select). Switches between Boost, Eco and Super Eco modes.
- `Hypervolt Max Current` (Number). Reads and sets the maximum charging current.
- `Hypervolt LED Brightness` (Numbers). Reads and sets the LED brightness, as avialable via Settings within the app\
  ℹ️ The LED Mode isn't currently supported by the integration
- `Hypervolt Charging Readiness` (Sensor). One of: `Charging`, `Ready` or `Not Ready - Force Stopped`\
  ⚠️ `Not Ready - Force Stopped` was added to overcome a gotcha with Hypervolt. If the user manually stops a charge by switching charging off via the app or integration, the Hypervolt charger remembers this state and if later is switched into Schedule Charge activation mode, the scheduled charge _will not automatically start_ as might be expected. To overcome this, the Charging switch needs to be manually toggled. This can be done when in Scheduled mode even outside of the schedule window and will switch the `Hypervolt Charging Readiness` state back to `Ready`. ⚠️ In the Hypervolt app, there doesn't appear to be a way of telling whether the charger is ready or not.
- `Hypervolt Voltage`, `Hypervolt CT Current`, `Hypervolt CT Power`, `Hypervolt Charger Current` (Sensors) are all measurements _only available during a charging session_ (sorry, you can't use this to measure your household consumption, unless you are charging all the time!). The CT Current and CT Power measurements come from the CT clamp, so measure potentially more than just the Hypervolt Charger load. `Hypervolt Charger Current` is just the charger current.
- `Hypervolt Session Energy`, `Hypervolt Session Carbon Saved`, `Hypervolt Session Money Spent`, `Hypervolt Session ID` (Sensors) are all fields related to the current, or most recent charging session. `Hypervolt Session Money Spent` is the figure given by the Hypervolt API and should match that in the app.

# Known limitations

- Only tested with a Hypervolt Home 2.0 charge point
- Only one charger per account supported. If you have more than one, only the first will be found
- Log in has to be via via email address and password. Google or Apple login not supported
- Spend is not calculated
- The charger name is not supported. The Device name in Home Assistant will be your charger's serial
- English language only
- Schedule _times_ cannot be read or set, only the Schedule _mode_ can be changed. I think we probably need [this](https://github.com/home-assistant/core/pull/81943) feature within Home Assistant, to allow integrations to use DateTime fields, before controlling the schedule is feasible. Unless you know better? 😉\
  ℹ️ You can of course now use Home Assistant to control starting and stopping your charger instead of relying on the Hypervolt schedule
- LED modes are not supported
- Installation of this integration is very basic. No HACS metadata. No icon
