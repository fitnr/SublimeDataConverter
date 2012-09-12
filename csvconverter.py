import sublime
import sublime_plugin
import csv
import os
import StringIO

"""
Freely adapted from Mr. Data Converter: http://shancarter.com/data_converter/
"""


class CsvConvertCommand(sublime_plugin.TextCommand):

    def run(self, edit, **kwargs):
        self.set_settings(kwargs)

        if self.view.sel()[0].empty():
            self.view.sel().add(sublime.Region(0, self.view.size()))
        for sel in self.view.sel():
            datagrid = self.import_csv(self.view.substr(sel).encode('utf-8'))
            self.view.replace(edit, sel, self.converter(datagrid))

        self.view.set_syntax_file(self.syntax)
        if self.settings.get('deselect', True):
            self.deselect()

    def set_settings(self, kwargs):
        formats = {
            "html": {'syntax': '../HTML/HTML.tmLanguage', 'function': self.html},
            "json": {'syntax': '../JavaScript/JavaScript.tmLanguage', 'function': self.json},
            "json (array of columns)": {'syntax': '../JavaScript/JavaScript.tmLanguage', 'function': self.jsonArrayCols},
            "json (array of rows)": {'syntax': '../JavaScript/JavaScript.tmLanguage', 'function': self.jsonArrayRows},
            "python": {'syntax': '../Python/Python.tmLanguage', 'function': self.python}
        }

        format = formats[kwargs['format']]
        self.converter = format['function']
        self.syntax = format['syntax']

        self.settings = sublime.load_settings('csvconverter.sublime-settings')

        # New lines
        self.newline = self.settings.get('line_sep', "\n")
        if self.newline == False:
            self.newline = os.line_sep

        # Indentation
        if (self.view.settings().get('translate_tabs_to_spaces')):
            self.indent = " " * int(self.view.settings().get('tab_size', 4))
        else:
            self.indent = "\t"

    def import_csv(self, selection):
        sample = selection[:1024]
        dialect = csv.Sniffer().sniff(sample)

        csvIO = StringIO.StringIO(selection)

        firstrow = sample.splitlines()[0].split(dialect.delimiter)

        if self.settings.get('assume_headers', True) or csv.Sniffer().has_header(sample):
            self.headers = firstrow
        else:
            self.headers = ["val" + str(x) for x in range(len(firstrow))]

        reader = csv.DictReader(
            csvIO,
            fieldnames=self.headers,
            dialect=dialect)

        if self.headers == firstrow:
            reader.next()

        return reader

    # Adapted from https://gist.github.com/1608283
    # Moved pointer to top of view
    def deselect(self):
        top = self.view.sel()[0].a
        self.view.sel().clear()
        self.view.sel().add(sublime.Region(top, top))

    # Helper for HTML converter
    def tr(self, string):
        return (self.indent * 2) + "<tr>" + self.newline + string + (self.indent * 2) + "</tr>" + self.newline

    # HTML Table
    def html(self, datagrid):
        nl = self.newline
        ind = self.indent

        table = "<table>" + nl
        table += ind + "<thead>" + nl + "{0}</thead>" + nl
        table += ind + "<tbody>" + nl + "{1}</tbody>" + nl
        table += "</table>"

        # Render table head
        thead = ""
        for header in self.headers:
            thead += (ind * 3) + '<th>' + header + '</th>' + nl
        thead = self.tr(thead)

        # Render table rows
        tbody = ""
        for row in datagrid:
            rowText = ""

            # Sadly, dictReader doesn't always preserve row order,
            # so we loop through the headers instead.
            for key in self.headers:
                rowText += (ind * 3) + '<td>' + row[key] + '</td>' + nl

            tbody += self.tr(rowText)

        return table.format(thead, tbody)

    # JSON properties
    def json(self, datagrid):
        import json
        return json.dumps([row for row in datagrid])

    # JSON Array of Columns
    def jsonArrayCols(self, datagrid):
        import json
        colDict = {}
        for row in datagrid:
            for key, item in row.iteritems():
                if key not in colDict:
                    colDict[key] = []
                colDict[key].append(item)
        return json.dumps(colDict)

    # JSON Array of Rows
    def jsonArrayRows(self, datagrid):
        import json
        rowArrays = []

        for row in datagrid:
            itemlist = []
            for item in row.itervalues():
                itemlist.append(item)
            rowArrays.append(itemlist)

        return json.dumps(rowArrays)

    # Python dict
    def python(self, datagrid):
        outDicts = []
        for row in datagrid:
            outDicts.append(row)
        return repr(outDicts)
