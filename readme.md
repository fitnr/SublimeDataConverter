# Sublime DataConverter

This [Sublime Text](http://www.sublimetext.com/) package converts csv files to various other formats. It's been adapted from the wonderful [Mr. Data Converter](https://shancarter.github.io/mr-data-converter/).

After installing, you'll find commands look like __DataConverter: to *foo*__ in the Command Palette. DataConverter will convert a selection or multiple selections. If nothing is selected, the entire document is converted.

### Examples

Turn this:

    NAME,VALUE,FRUIT,DATE
    Alice,10,Apple,"Sep. 12, 2012"
    Bob,11,Blueberry,"Sep. 13, 2012"
    Chris,12,Orange,"Sep. 14, 2012"

into this (Ruby):

```ruby
[{"NAME"=>"Alice", "VALUE"=>10, "FRUIT"=>"Apple", "DATE"=>"Sep. 12, 2012"},
{"NAME"=>"Bob", "VALUE"=>11, "FRUIT"=>"Blueberry", "DATE"=>"Sep. 13, 2012"},
{"NAME"=>"Chris", "VALUE"=>12, "FRUIT"=>"Orange", "DATE"=>"Sep. 14, 2012"}];
```

or this (JSON):

```javascript
[
  {"FRUIT": "Apple", "NAME": "Alice", "VALUE": "10", "DATE": "Sep. 12, 2012"},
  {"FRUIT": "Blueberry", "NAME": "Bob", "VALUE": "11", "DATE": "Sep. 13, 2012"},
  {"FRUIT": "Orange", "NAME": "Chris", "VALUE": "12", "DATE": "Sep. 14, 2012"}
]
```

### Formats supported

* ActionScript
* ASP
* HTML tables
* Gherkin
* JIRA (Atlassian Confluence)
* JSON
* JSON (array of columns)
* JSON (array of rows)
* JSON (object, first column is key)
* Javascript object
* MySQL
* Perl
* PHP (two formats)
* Python (list of dicts)
* Python (list of lists)
* Ruby
* text table
* Wiki markup
* XML
* XML (property list)
* XML for data-driven Adobe Illustrator
* YAML

### Configuration
Check out `DataConverter.sublime-settings` for a documented list of options.

## Installation

### With Package Control
If you have [Package Control](http://github.com/wbond/sublime_package_control) installed, you can install DataConverter from within Sublime Text 2. Open the Command Palette and enter "Package Control: Install Package", then search for __DataConverter__.

### Without Package Control
Clone the repository into your Sublime Text 2 packages directory:

    git clone git://github.com/fitnr/SublimeDataConverter.git

### Without Package Control or Git
Click `Download Zip` above to download the package. Unzip it, rename the folder "DataConverter" and move it into your Sublime Text 2 packages directory (*Preferences > Browse Packages* in the application menu).

## Limitations

CSV containing Unicode characters aren't supported in the Sublime Text 2 version of the package. This is due to limitations in the Python 2.6 csv module. Unicode is fully supported in the Sublime Text 3 version of the package.

## Problems?

[Submit an issue](https://github.com/fitnr/SublimeDataConverter/issues).

## Contributing

Pull requests with additional formats are encouraged. The YAML converter is well-commented as an introduction to how the package works.
