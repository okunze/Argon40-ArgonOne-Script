# Argon ONE (V2) Pi 4 Script

I have been using the [Argon ONE (V2) Case for Raspberry Pi 4](https://www.argon40.com/collections/raspberry-pi-cases "Argon ONE (V2) Case for Raspberry Pi 4") for a long time and I am very happy with it.

To be able to use the case to the full extent, it is recommended to install the [script](https://download.argon40.com/argon1.sh "https://download.argon40.com/argon1.sh") offered by [Argon 40](https://www.argon40.com "https://www.argon40.com").

I have saved a copy here along with the instructions to have a copy in case [Argon 40](https://www.argon40.com "https://www.argon40.com") no longer offers it themselves.

**Just to clarify: I am in no way affiliated with [Argon 40](https://www.argon40.com "https://www.argon40.com"), I only use their cases as an end user.**


You can find them here:
* Argon 40 Website: [https://www.argon40.com](https://www.argon40.com "https://www.argon40.com")
* Argon 40 Github: [https://github.com/Argon40Tech](https://github.com/Argon40Tech "https://github.com/Argon40Tech")

## How to install Argon ONE (V2) Pi 4 Power Button & Fan Control

### Prerequisites

* [Raspberry Pi 4 Model B (2GB, 4GB or 8GB version)](https://www.raspberrypi.org/products/raspberry-pi-4-model-b/ "Raspberry Pi 4 Model B")
* [Raspberry Pi OS (previously called Raspbian)](https://www.raspberrypi.org/downloads/ "Raspberry Pi OS") installed on microSD card
* [Argon ONE (V2) Case for Raspberry Pi 4](https://www.argon40.com/collections/raspberry-pi-cases "Argon ONE (V2) Case for Raspberry Pi 4")

### Installing

1. Connect to the internet.
2. Open "Terminal" in Raspbian.
3. Type the text below in the "Terminal" to initiate installation of Argon ONE (V2) Pi 4 script.

   ```
   curl https://download.argon40.com/argon1.sh | bash
   ```

4. Reboot.

## Usage Instructions

### Argon ONE (V2) Pi 4 Power Button Functions

ARGON ONE (V2) PI 4 STATE | ACTION | FUNCTION
:------------------: | :----: | :------:
OFF | Short Press | Turn ON
ON | Long Press (>= 3 s) | Soft Shutdown and Power Cut
ON | Short Press (< 3 s) | Nothing
ON | Double Tap | Reboot
ON | Long Press (>= 5 s) | Forced Shutdown

### Argon ONE (V2) Pi 4 Fan Speed
Upon installation of the Argon ONE (V2) Pi 4 script by default, the settings of the Argon ONE (V2) Pi 4 cooling system are as follows:

CPU TEMP | FAN POWER
:------: | :-------:
55 C | 30%
60 C | 55%
65 C | 100%

However, you may change or configure the FAN to your desired settings by clicking the Argon ONE (V2) Pi 4 Config icon on your Desktop.

Or via "Terminal" by typing and following the specified format:

```
argonone-config
```

## Uninstalling Argon ONE (V2) Pi 4 Script

To uninstall the Argon ONE (V2) Pi 4 script you may do so by clicking the Argon One (V2) Pi 4 Uninstall icon on your Desktop.

You may also remove the script via "Terminal" by typing.
```
argonone-uninstall
```

Always reboot after changing any configuration or uninstallation for the revised settings to take effect.

## Built With

* [Danny Guo / Make a README](https://www.makeareadme.com/ "Make a README") - The README generator used for README.md
* [PurpleBooth / README-Template.md](https://gist.github.com/PurpleBooth/109311bb0361f32d87a2 "PurpleBooth / README-Template.md") - The template used for README.md
* [Adam Pritchard / Markdown Cheatsheet](https://github.com/adam-p/markdown-here/wiki/Markdown-Cheatsheet "Markdown Cheatsheet") - The Markdown Cheatsheet used for README.md
* [Matt Cone / The Markdown Guide](https://www.markdownguide.org/ "The Markdown Guide") - The Markdown Guide used for README.md

## Acknowledgments

Thanks to [Argon 40](https://www.argon40.com "https://www.argon40.com") for building these great Raspberry Pi Cases.

---

### Alternatives

A fan control daemon written in Rust for Argon One v2 case: [JhnW/ArgonOne-Native-Fan-Controller](https://github.com/JhnW/ArgonOne-Native-Fan-Controller "JhnW/ArgonOne-Native-Fan-Controller")
