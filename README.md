# inventree-dymo-550-plugin

![Static Badge](https://img.shields.io/badge/License-MIT-blue)

A label printer driver plugin for [InvenTree](https://inventree.org/), which
provides support for Dymo Label Writer® 550-series printers.

This driver is roughly based on wolflu05's [Dymo 450
driver](https://github.com/wolflu05/inventree-dymo-plugin), but the interactive
nature of the 550's network protocol requires a somewhat different code
structure.

## Compatibility

The following printers have been tested:

- DYMO Label Writer 550 (Turbo)
- DYMO Label Writer 5XL

## Connectivity

This driver connects directly to the printers over a network connection.

It may be possible to expose a USB-connected printer as a network using using `xinetd` like as described in this [blog
post](https://nerdig.es/labelwriter-im-netz-teil1/).

## Installation

> [!IMPORTANT]
> This plugin is only compatible with InvenTree>=0.16 because this uses the new
label printer driver interface introduced with
[inventree/InvenTree#4824](https://github.com/inventree/InvenTree/pull/4824) and
was fixed with 0.16 to work inside of workers.

Goto "Admin Center > Plugins > Install Plugin" and enter `inventree-dymo-550-plugin` as the package name.

Then goto "Admin Center > Machines" and create a new machine using this driver.

## Technical Resources

Readers may wish to refer to the [LabelWriter® 550 technical
reference](https://download.dymo.com/dymo/user-guides/LabelWriter/LW550Series/LW%20550%20Technical%20Reference.pdf).

The
[`dymosoftware`](https://github.com/dymosoftware/Drivers/tree/main/LW5xx_Linux/src/lw)
GitHub repository also contains a CUPS driver which can provide additional
technical resources.

## Disclaimer

This work is wholly unaffiliated with Newell Brands, the owners of the Dymo LabelMaker trademarks.