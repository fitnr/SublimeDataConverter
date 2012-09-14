# Sublime DataConverter

This is a [Sublime Text 2](http://www.sublimetext.com/) package for converting csv files to various other formats. It's been adapted from the wonderful [Mr. Data Converter](http://shancarter.com/data_converter/).

## What it does
It converts comma-separated or tab-separated data into many formats. Actually, just about any separator or line ending will be tolerated.

You'll find commands look like __DataConverter: to *foo*__ in the Command Palette. DataConverter will convert a selection or multiple selections. If nothing is selected, the entire document is converted.

Formats supported: 
* ActionScript
* ASP
* HTML tables
* JSON
* JSON (array of columns)
* JSON (array of rows)
* MySQL
* PHP
* Python
* Ruby
* XML
* XML (property list)
 
### Example

Turn this:

    NAME,VALUE,FRUIT,DATE
    Steve,10,Apple,"Sep. 12, 2012"
    Todd,11,Blueberry,"Sep. 13, 2012"
    Bob,12,Orange,"Sep. 14, 2012"

Into this (Ruby):

```ruby
[{"NAME"=>Steve, "VALUE"=>"10", "FRUIT"=>"Apple", "DATE"=>"Sep. 12, 2012"},
{"NAME"=>Todd, "VALUE"=>"11", "FRUIT"=>"Blueberry", "DATE"=>"Sep. 13, 2012"},
{"NAME"=>Bob, "VALUE"=>"12", "FRUIT"=>"Orange", "DATE"=>"Sep. 14, 2012"}];
```

or this (JSON):

```javascript
[{"DATE": "Sep. 12, 2012", "FRUIT": "Apple", "NAME": "Steve", "VALUE": "10"},
{"DATE": "Sep. 13, 2012", "FRUIT": "Blueberry", "NAME": "Todd", "VALUE": "11"},
{"DATE": "Sep. 14, 2012", "FRUIT": "Orange", "NAME": "Bob", "VALUE": "12"}]
```

### Configuration
Check out `DataConverter.sublime-settings` for a documented list of options.

## Installation

### With Package Control
If you have [Package Control](http://github.com/wbond/sublime_package_control) installed, you can install DataConverter from within Sublime Text 2. Open the Command Palette and enter "Package Control: Install Package", then search for __DataConverter__.

### Without Package Control
Clone the repository into your Sublime Text 2 packages directory:

    git clone git://github.com/fitnr/SublimeDataConverter.git

### Without Package Control or Git
[Go to the download section](http://github.com/fitnr/SublimeDataConverter/downloads) and download the package. Unzip it, rename the folder "DataConverter" and move it into your Sublime Text 2 packages directory (*Preferences > Browse Packages* in the menu).
