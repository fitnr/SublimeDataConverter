"""
DataConverter package for Sublime Text 2
https://github.com/fitnr/SublimeDataConverter

Freely adapted from Mr. Data Converter: http://shancarter.com/data_converter/
"""

import sublime
import sublime_plugin
import csv
import os
import StringIO

PACKAGES = sublime.packages_path()


class DataConverterCommand(sublime_plugin.TextCommand):

    def run(self, edit, **kwargs):
        try:
            self.get_settings(kwargs)
        except Exception as e:
            print "DataConverter: error fetching settings. Did you specify a format?", e
            return

        if self.view.sel()[0].empty():
            self.view.sel().add(sublime.Region(0, self.view.size()))
            deselect_flag = True

        for sel in self.view.sel():
            selection = self.view.substr(sel).encode('utf-8')
            data = self.import_csv(selection)
            converted = self.converter(data)
            self.view.replace(edit, sel, converted)
            deselect_flag = False

        if self.syntax is not None:
            self.view.set_syntax_file(self.syntax)

        if deselect_flag or self.settings.get('deselect_after'):
            self.deselect()

    def get_settings(self, kwargs):
        # Adding a format? Check if it belongs in no_space_formats and no_type_formats.
        formats = {
            "actionscript": self.actionscript,
            "asp": self.asp,
            "html": self.html,
            "json": self.json,
            "json_columns": self.jsonArrayCols,
            "json_rows": self.jsonArrayRows,
            "mysql": self.mysql,
            "php": self.php,
            "python": self.python,
            "ruby": self.ruby,
            "xml": self.xml,
            "xml_properties": self.xmlProperties
        }

        self.converter = formats[kwargs['format']]

        # This will be set later on, in the converter function
        self.syntax = None

        self.settings = sublime.load_settings('DataConverter.sublime-settings')

        # Combine headers for xml formats
        no_space_formats = ['actionscript', 'mysql', 'xml', 'xml_properties']
        mergeheaders = kwargs['format'] in no_space_formats
        self.settings.set('mergeheaders', mergeheaders)

        # Don't like having 'not' in the assignment, but it's less error prone to
        # specify the formats that don't need a feature, rather than those that do.
        no_type_formats = ["html", "json", "json_columns", "json_rows", "python", "xml", "xml_properties"]
        get_types = kwargs['format'] in no_type_formats
        self.settings.set('gettypes', not get_types)

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
        try:
            dialect = csv.Sniffer().sniff(sample)
        except Exception as e:
            delimiter = self.settings.get('delimiter', ',')
            delimiter = bytes(delimiter[0])  # dialect definition takes a 1-char bytestring
            print "DataConverter had trouble sniffing:", e
            try:
                csv.register_dialect('barebones', delimiter=delimiter)
            except Exception as e:
                print e, ": '" + delimiter + "'"

            dialect = csv.get_dialect('barebones')

        csvIO = StringIO.StringIO(selection)

        firstrow = sample.splitlines()[0].split(dialect.delimiter)

        # Replace spaces in the header names for some formats.
        if self.settings.get('mergeheaders', False) is True:
            firstrow = [x.replace(' ', '_') for x in firstrow]

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
            header_flag = True

        # Having separate headers and types lists is a bit clumsy,
        # but a dict wouldn't  keep track of the order of the fields.
        # A slightly better way would be to use an OrderedDict, but this is more compatible with older Pythons.
        if self.settings.get('gettypes', True) is True:
            self.types = self.parse(reader, self.headers)

            # Fetching types messes up the pointer, reset it.
            csvIO.seek(0)
            if header_flag:
                reader.next()

        return reader

    def deselect(self):
        """Remove selection and place pointer at top of document (adapted from https://gist.github.com/1608283)."""
        top = self.view.sel()[0].a
        self.view.sel().clear()
        self.view.sel().add(sublime.Region(top, top))

    # data type parser
    # ==================

    def parse(self, reader, headers):
        """ Return a list containing a best guess for the types of data in each column. """
        output_types, types, k = [], [], len(headers)

        for n in range(10):
            try:
                row = reader.next()
            except:
                break

            tmp = []

            for h in headers:
                typ = self.get_type(row[h])
                tmp.append(typ)

            types.append(tmp)

        #rotate the array
        types = zip(*types)

        for header, type_list in zip(headers, types):
            if str in type_list:
                output_types.append(str)
            elif float in type_list:
                output_types.append(float)
            else:
                output_types.append(int)

        return output_types

    def get_type(self, datum):
        """ Select a data type from a (string) input"""
        try:
            int(datum)
            return int
        except:
            try:
                float(datum)
                return float
            except:
                return str

    # Converters
    # ==========

    # Note that converters should assign a syntax file path to self.syntax.

    def type_loop(self, row, form, nulltxt='null'):
        """
        Helper loop for checking types as we write out a row.
        Strings get quoted, floats and ints don't.
        row is a dictionary returned from DictReader
        Returns a line of code in format form (e.g. "{0}=>{1}, ")

        """
        out = ''
        for key, typ in zip(self.headers, self.types):
            if typ == str:
                txt = '"' + row[key] + '"'
            elif row[key] is None:
                txt = nulltxt
            else:
                txt = row[key]

            out += form.format(key, txt)
        return out

    def actionscript(self, datagrid):
        """Actionscript converter"""
        #self.syntax = PACKAGES + '/ActionScript/ActionScript.tmLanguage'
        output = "["

        #begin render loops
        for row in datagrid:
            output += "{"
            output += self.type_loop(row, '{0}:{1},')

            output = output[0:-1] + "}" + "," + self.newline

        return output[:-2] + "];"

    # ASP / VBScript
    def asp(self, datagrid):
        self.syntax = PACKAGES + '/ASP/ASP.tmLanguage'
        #comment, comment_end = "'", ""
        output, r = "", 0
        zipper = zip(range(len(self.headers)), self.headers, self.types)
        #print self.headers, self.types

        #begin render loop
        for row in datagrid:

            for c, key, item_type in zipper:

                if item_type == str:
                    row[key] = '"' + (row[key] or "") + '"'
                if item_type is None:
                    row[key] = 'null'

                output += 'myArray({0},{1}) = {2}'.format(c, r, row[key] + self.newline)
            r = r + 1

        dim = 'Dim myArray({0},{1}){2}'.format(c, r - 1, self.newline)

        return dim + output

    def tr(self, row):
        """Helper for HTML converter"""
        return (self.indent * 2) + "<tr>" + self.newline + row + (self.indent * 2) + "</tr>" + self.newline

    def html(self, datagrid):
        """HTML Table converter"""
        self.syntax = PACKAGES + '/HTML/HTML.tmLanguage'

        nl, ind = self.newline, self.indent

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
                rowText += (ind * 3) + '<td>' + (row[key] or "") + '</td>' + nl

            tbody += self.tr(rowText)

        return table.format(thead, tbody)

    def json(self, datagrid):
        """JSON properties converter"""
        import json
        self.syntax = PACKAGES + '/JavaScript/JavaScript.tmLanguage'

        return json.dumps([row for row in datagrid])

    def jsonArrayCols(self, datagrid):
        """JSON Array of Columns converter"""
        import json
        self.syntax = PACKAGES + '/JavaScript/JavaScript.tmLanguage'
        colDict = {}

        for row in datagrid:
            for key, item in row.iteritems():
                if key not in colDict:
                    colDict[key] = []
                colDict[key].append(item)
        return json.dumps(colDict)

    def jsonArrayRows(self, datagrid):
        """JSON Array of Rows converter"""
        import json
        self.syntax = PACKAGES + '/JavaScript/JavaScript.tmLanguage'
        rowArrays = []

        for row in datagrid:
            itemlist = []
            for item in row.itervalues():
                itemlist.append(item)
            rowArrays.append(itemlist)

        return json.dumps(rowArrays)

    def mysql(self, datagrid):
        """MySQL converter"""
        self.syntax = PACKAGES + '/SQL/SQL.tmLanguage'

        table = 'DataConverter'

        # CREATE TABLE statement
        create = 'CREATE TABLE ' + table + '(' + self.newline
        create += self.indent + "id INT NOT NULL AUTO_INCREMENT PRIMARY KEY," + self.newline

        # INSERT TABLE Statement
        insert = 'INSERT INTO ' + table + " " + self.newline + self.indent + "("

        # VALUES list
        values = "VALUES" + self.newline

        # Loop through headers
        for header, typ in zip(self.headers, self.types):
            if typ == str:
                typ = 'VARCHAR(255)'
            elif typ == float:
                typ = 'FLOAT'
            elif typ == int:
                typ = 'INT'

            insert += header + ","

            create += self.indent + header + " " + typ + "," + self.newline

        create = create[:-2] + self.newline  # Remove the comma and newline
        create += ');' + self.newline

        insert = insert[:-1] + ") " + self.newline

        # loop through rows
        for row in datagrid:
            values += self.indent + "("
            values += self.type_loop(row, form='{1},')

            values = values[:-1] + '),' + self.newline

        return create + insert + values[:-2] + ';'

    def php(self, datagrid):
        """PHP converter"""
        self.syntax = PACKAGES + '/PHP/PHP.tmLanguage'
        #comment, comment_end = "//", ""
        output = "$DataConverter = array(" + self.newline

        #begin render loop
        for row in datagrid:
            output += self.indent + "array("
            output += self.type_loop(row, '"{0}"=>{1}, ')

            output = output[:-2] + ")," + self.newline

        return output[:-1] + self.newline + ");"

    def python(self, datagrid):
        """Python dict converter"""
        self.syntax = PACKAGES + '/Python/Python.tmLanguage'
        out = []
        for row in datagrid:
            out.append(row)
        return repr(out)

    def ruby(self, datagrid):
        """Ruby converter"""
        self.syntax = PACKAGES + '/Ruby/Ruby.tmLanguage'
        #comment, comment_end = "#", ""
        output, tableName = "[", "DataConverter"

        #begin render loop
        for row in datagrid:
            output += "{"
            output += self.type_loop(row, '"{0}"=>{1}, ', nulltxt='nil')

            output = output[:-2] + "}," + self.newline

        return output[:-2] + "];"

    def xml(self, datagrid):
        """XML Nodes converter"""
        self.syntax = PACKAGES + '/XML/XML.tmLanguage'
        output_text = '<?xml version="1.0" encoding="UTF-8"?>' + self.newline
        output_text += "<rows>" + self.newline

        #begin render loop
        for row in datagrid:
            output_text += self.indent + "<row>" + self.newline
            for header in self.headers:
                line = (self.indent * 2) + '<{1}>{0}</{1}>' + self.newline
                item = row[header] or ""
                output_text += line.format(item, header)
            output_text += self.indent + "</row>" + self.newline

        output_text += "</rows>"

        return output_text

    def xmlProperties(self, datagrid):
        """XML properties converter"""
        self.syntax = PACKAGES + '/XML/XML.tmLanguage'
        output_text = '<?xml version="1.0" encoding="UTF-8"?>' + self.newline
        output_text += "<rows>" + self.newline

        #begin render loop
        for row in datagrid:
            row_list = []

            for header in self.headers:
                item = row[header] or ""
                row_list.append('{0}="{1}"'.format(header, item))
                row_text = " ".join(row_list)

            output_text += self.indent + "<row " + row_text + "></row>" + self.newline

        output_text += "</rows>"

        return output_text
