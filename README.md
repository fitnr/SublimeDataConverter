# Sublime DataConverter

This [Sublime Text](http://www.sublimetext.com/) package converts csv files to various other formats. It's been adapted from the wonderful [Mr. Data Converter](https://shancarter.github.io/mr-data-converter/).

After installing, you'll find commands look like __DataConverter: to *foo*__ in the Command Palette. DataConverter will convert a selection or multiple selections. If nothing is selected, the entire document is converted.

### Examples

Turn this:

    name,value,fruit,date
    Alice,10,Apple,"Sep. 12, 2016"
    Bob,11,Blueberry,"Sep. 13, 2016"
    Chris,12,Orange,"Sep. 14, 2016"

into this (Ruby):

```ruby
[{"name"=>"Alice", "value"=>10, "fruit"=>"Apple", "date"=>"Sep. 12, 2016"},
{"name"=>"Bob", "value"=>11, "fruit"=>"Blueberry", "date"=>"Sep. 13, 2016"},
{"name"=>"Chris", "value"=>12, "fruit"=>"Orange", "date"=>"Sep. 14, 2016"}];
```

or this (JSON):

```javascript
[
  {"fruit": "Apple", "name": "Alice", "value": "10", "date": "Sep. 12, 2016"},
  {"fruit": "Blueberry", "name": "Bob", "value": "11", "date": "Sep. 13, 2016"},
  {"fruit": "Orange", "name": "Chris", "value": "12", "date": "Sep. 14, 2016"}
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
* Perl
* PHP (two formats)
* Python (list of dicts)
* Python (list of lists)
* Ruby
* SQL (Postgres, MySQL and SQLite)
* text table
* Wiki markup
* XML
* XML (property list)
* XML for data-driven Adobe Illustrator
* YAML

Additionally, DataConverter can convert between delimiters. By default, this includes commands to convert to CSV and TSV, and it's possible to add your own delimiter (create a `User.sublime-commands` file following the pattern in [`DataConverter.sublime-commands`](DataConverter.sublime-commands)).

## Installation

### With Package Control
If you have [Package Control](http://github.com/wbond/sublime_package_control) installed, you can install DataConverter from within Sublime Text. Open the Command Palette and enter "Package Control: Install Package", then search for __DataConverter__.

### Without Package Control
Clone the repository into your Sublime Text packages directory:

    git clone git://github.com/fitnr/SublimeDataConverter.git

### Without Package Control or Git
Click `Download Zip` above to download the package. Unzip it, rename the folder "DataConverter" and move it into your Sublime Text 2 packages directory (*Preferences > Browse Packages* in the application menu).

## Limitations

CSV containing Unicode characters aren't supported in the Sublime Text 2 version of the package. This is due to limitations in the Python 2.6 csv module. Unicode is fully supported in the Sublime Text 3 version of the package.

## Problems?

[Submit an issue](https://github.com/fitnr/SublimeDataConverter/issues).

## Contributing

Pull requests with additional formats are encouraged.

## Configuration

DataConverter reads the following options from your settings file (Preferences > Package Settings > DataConverter > Settings - User).

#### headers
Possible values: `"sniff"`, `true`, or `false`.
````
"headers": "sniff"
````
When true, the first row is always treated as the header row. When "sniff", DataConverter will sniff for headers (sniffing isn't perfect). When false, DataConverter will assume there are no headers, and use default headers (`[val1, val2, ...]`).

#### line_sep
Character or null
````
"line_sep": null
````
Newline character for output. Set to either a character or `null`. When `null`, DataConverter uses the OS line separator, which is `"\r"` in Windows.

#### dialects
Object
````
"dialects": {
  "example": {
    "delimiter": ",",
    "quotechar": "\"",
    "escapechar": "\\",
    "doublequote": false
    "skipinitialspace": false,
    "strict": false,
    "quoting": "QUOTE_MINIMAL"
  }
}
````
Defines a dialect for the CSV reader. Check the python docs for a [description of how to define a dialect](https://docs.python.org/3.3/library/csv.html#dialects-and-formatting-parameters).

DataConverter will try to detect a dialect, but it may fail. Define a dialect with this setting and then tell DataConverter to use it with the `use_dialect` option.

Note that Python's csv reader is hard-coded to recognise either '\r' or '\n' as end-of-line, and ignores lineterminator.

#### use_dialect
String
````
"use_dialect": "example"
````
Mandate a dialect for DataConverter to use. Could be a dialect defined in your settings file, or one defined in the csv module ("excel", "excel_tab", "unix_dialect"). This may be useful for specifying custom commands in a `.sublime-commands` file.

#### html_utf8
Boolean
````
"html_utf8": true
````
Modern HTML served with a proper character encoding can accept UTF-8 characters. If you're using another charset for your html, set this to `false`. When `false`, the 'DataConverter: to HTML Table' function will escape non-ascii characters (e.g. `&ndash;` for –). (XML is always returned with escaped characters.)


#### delimiter
Character
````
"delimiter": ","
````
DataConverter will try to detect the delimiter used in your data. If it has a problem, it will fall back on this value. This must be one character long. Use `"\t"` for tab.

#### header_joiner
String
````
"header_joiner": "_"
````
For formats where keys can't have spaces, field names will be joined with this character. By default, an underscore is used, e.g. 'Col Name' becomes 'Col_Name'. An empty string is OK.

#### deselect_after
Boolean
````
"deselect_after": false
````
If `true`: after converting, deselects and moves the pointer to the top. If `false`: leaves selection(s) in place

#### default_variable
````
"default_variable": "DataConverter"
````
For some conversions (SQL, ASP), DataConverter must name the table or array being created. By default, it's called 'DataConverter', any string value is accepted.

