# Sublime DataConverter

This [Sublime Text 2](http://www.sublimetext.com/) package converts csv files to various other formats. It's been adapted from the wonderful [Mr. Data Converter](http://shancarter.com/data_converter/).

After installing, you'll find commands look like __DataConverter: to *foo*__ in the Command Palette. DataConverter will convert a selection or multiple selections. If nothing is selected, the entire document is converted.

### Examples

Turn this:

    NAME,VALUE,FRUIT,DATE
    Steve,10,Apple,"Sep. 12, 2012"
    Todd,11,Blueberry,"Sep. 13, 2012"
    Bob,12,Orange,"Sep. 14, 2012"

into this (Ruby):

```ruby
[{"NAME"=>"Steve", "VALUE"=>10, "FRUIT"=>"Apple", "DATE"=>"Sep. 12, 2012"},
{"NAME"=>"Todd", "VALUE"=>11, "FRUIT"=>"Blueberry", "DATE"=>"Sep. 13, 2012"},
{"NAME"=>"Bob", "VALUE"=>12, "FRUIT"=>"Orange", "DATE"=>"Sep. 14, 2012"}];
```

or this (JSON):

```javascript
[{"DATE": "Sep. 12, 2012", "FRUIT": "Apple", "NAME": "Steve", "VALUE": "10"},
{"DATE": "Sep. 13, 2012", "FRUIT": "Blueberry", "NAME": "Todd", "VALUE": "11"},
{"DATE": "Sep. 14, 2012", "FRUIT": "Orange", "NAME": "Bob", "VALUE": "12"}]
```

### Formats supported

* ActionScript
* ASP
* HTML tables
* JIRA (Atlassian Confluence)
* JSON
* JSON (array of columns)
* JSON (array of rows)
* Javascript object
* MySQL
* Perl
* PHP
* Python (list of dicts)
* Python (list of lists)
* Ruby
* text table
* Wiki markup
* XML
* XML (property list)

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

## Problems?

[Submit an issue](https://github.com/fitnr/SublimeDataConverter/issues).
