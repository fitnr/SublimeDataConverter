# Sublime DataConverter

This is a (Sublime Text 2)[http://www.sublimetext.com/] package for converting csv files to various other formats. It's been adapted from the wonderful [Mr. Data Converter](http://shancarter.com/data_converter/).

## What is does
It converts CSVs or TSVs into many formats. Actually, just about any separator or line ending will be tolerated.

You'll find commands look like *Convert CSV to foo* in the Command Palette. Sublime DataConverter will convert a selection or multiple selections. If nothing is selected, the entire document is converted.

Formats supported: 
	*ActionScript
	*ASP
	*HTML tables
	*JSON
	*JSON (array of columns)
	*JSON (array of rows)
	*MySQL
	*PHP
	*python
	*Ruby
	*XML
	*XML (property list)

### Configuration
By default, Sublime DataConverter is Check out `csvconverter.sublime-settings` for a documented list of options.

## Installation

### With Package Control
If you have [Package Control][http://github.com/wbond/sublime_package_control] installed, you can install Sublime DataConverter from within Sublime Text 2. Open the Command Palette and enter "Package Control: Install Package", then search for *CSV Converter*.

### Without Package Control
You should probably just install Package Control, it's pretty great.
Clone the repository into your Sublime Text 2 packages directory:

    git clone git://github.com/fitnr/SublimeCSVConverter.git

### Without Package Control or Git
[Go to the download section](http://github.com/fitnr/SublimeCSVConverter/downloads) and download the package. Unzip it, rename the folder "CSVConverter" and move it into your Sublime Text 2 packages directory (*Preferences > Browse Packages* in the menu).
