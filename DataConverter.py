# -*- coding: utf-8 -*-
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


def UnicodeDictReader(data, encoding='utf-8', **kwargs):
    '''Adapted from:
    http://stackoverflow.com/questions/5478659/python-module-like-csv-dictreader-with-full-utf8-support'''
    csv_reader = csv.DictReader(data, **kwargs)
    # Unlike the example, we know that our field names are already unicode
    # So need not decode them.
    keymap = dict((k, k) for k in csv_reader.fieldnames)

    for row in csv_reader:
        yield dict((keymap[k], v.decode(encoding)) for k, v in row.iteritems())


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
            selection = self.view.substr(sel)
            sample = selection[:1024]
            self.dialect = self.sniff(sample)
            # Having separate headers and types lists is a bit clumsy,
            # but a dict wouldn't keep track of the order of the fields.
            # A slightly better way would be to use an OrderedDict, but this is more compatible with older Pythons.

            self.headers = self.assign_headers(sample)

            data = self.import_csv(selection)
            converted = self.converter(data)
            self.view.replace(edit, sel, converted)
            deselect_flag = False

        if self.syntax is not None:
            self.view.set_syntax_file(self.syntax)

        if deselect_flag or self.settings.get('deselect_after'):
            self.deselect()

    def get_settings(self, kwargs):
        # Adding a format? Check if it belongs in no_space_formats and untyped_formats.
        formats = {
            "actionscript": self.actionscript,
            "asp": self.asp,
            "html": self.html,
            "javascript": self.javascript,
            "json": self.json,
            "json_columns": self.jsonArrayCols,
            "json_rows": self.jsonArrayRows,
            "mysql": self.mysql,
            "php": self.php,
            "python_dict": self.python_dict,
            "python_list": self.python_list,
            "ruby": self.ruby,
            "xml": self.xml,
            "text_table": self.text_table,
            "xml_properties": self.xmlProperties
        }

        self.converter = formats[kwargs['format']]

        # This will be set later on, in the converter function
        self.syntax = None

        self.settings = sublime.load_settings('DataConverter.sublime-settings')

        # Combine headers for xml formats
        no_space_formats = ['actionscript', 'javascript', 'mysql', 'xml', 'xml_properties']
        mergeheaders = kwargs['format'] in no_space_formats
        self.settings.set('mergeheaders', mergeheaders)

        untyped_formats = ["html", "json", "json_columns", "json_rows", "text_table", "xml", "xml_properties"]
        # Don't like having 'not' in this expression, but it makes more sense to use 'typed' from here on out
        # And it's less error prone to use the (smaller) list of untyped formats
        typed = kwargs['format'] not in untyped_formats
        self.settings.set('typed', typed)

        # New lines
        self.newline = self.settings.get('line_sep', False)
        if self.newline is False:
            self.newline = os.linesep

        # Indentation
        if (self.view.settings().get('translate_tabs_to_spaces')):
            self.indent = u" " * int(self.view.settings().get('tab_size', 4))
        else:
            self.indent = u"\t"

        # HTML characters
        self.html_utf8 = self.settings.get('html_utf8', False)

        # Dialect
        if (self.settings.get('use_dialect')):
            dialectname = self.settings.get('use_dialect')
            try:
                self.dialect = csv.get_dialect(dialectname)
            except Exception:
                user_dialects = self.settings.get('dialects')

                try:
                    try:
                        user_dialects[dialectname]["delimiter"] = bytes(user_dialects[dialectname]["delimiter"][0])
                    except Exception:
                        pass
                    try:
                        user_dialects[dialectname]["quotechar"] = bytes(user_dialects[dialectname]["quotechar"][0])
                    except Exception:
                        pass

                    csv.register_dialect(dialectname, **user_dialects[dialectname])
                    self.dialect = csv.get_dialect(dialectname)
                except Exception:
                    self.dialect = None
                    print 'DataConverter could not find', dialectname, ". Will try to sniff for a dialect"
        else:
            self.dialect = None

    def sniff(self, sample):
        if self.dialect:
            return self.dialect

        try:
            dialect = csv.Sniffer().sniff(sample)
            print 'DataConverter is using this delimiter:', dialect.delimiter
            return dialect
        except Exception as e:
            print "DataConverter had trouble sniffing:", e
            delimiter = self.settings.get('delimiter', ',')
            delimiter = bytes(delimiter)  # dialect definition takes a 1-char bytestring
            try:
                csv.register_dialect('barebones', delimiter=delimiter)
                return csv.get_dialect('barebones')

            except Exception as e:
                return csv.get_dialect('excel')

    def assign_headers(self, sample):
        '''Mess with headers, merging and stripping as needed.'''
        firstrow = sample.splitlines().pop(0).split(self.dialect.delimiter)

        if self.settings.get('assume_headers', None) or csv.Sniffer().has_header(sample):
            headers = firstrow
            self.settings.set('has_header', True)

            # Replace spaces in the header names for some formats.
            if self.settings.get('mergeheaders', False) is True:
                hj = self.settings.get('header_joiner', '')
                headers = [x.replace(' ', hj) for x in headers]

            if self.settings.get('strip_quotes', None):
                headers = [j.strip('"\'') for j in headers]

        else:
            headers = ["val" + str(x) for x in range(len(firstrow))]

        return headers

    def import_csv(self, selection):
        # Remove header from entries that came with one.
        if self.settings.get('has_header', False) is True:
            selection = selection[selection.find(self.newline):]

        selection = selection.encode('utf-8')
        csvIO = StringIO.StringIO(selection)

        reader = UnicodeDictReader(
            csvIO,
            encoding='utf-8',
            fieldnames=self.headers,
            dialect=self.dialect)

        if self.settings.get('typed', False) is True:
            # Another reader for checking field types.
            typerIO = StringIO.StringIO(selection)
            typer = csv.DictReader(typerIO, fieldnames=self.headers, dialect=self.dialect)
            self.types = self.parse(typer, self.headers)

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
        output_types, types = [], []

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

        print 'DataConverter found these output types:', output_types
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
        out = u''
        for key, typ in zip(self.headers, self.types):
            if row[key] is None:
                txt = nulltxt
            elif typ == str:
                txt = u'"' + row[key] + '"'
            else:
                txt = row[key]

            out += form.format(key, txt)
        return out

    def actionscript(self, datagrid):
        """Actionscript converter"""
        self.syntax = PACKAGES + '/ActionScript/ActionScript.tmLanguage'
        output = u"["

        #begin render loops
        for row in datagrid:
            output += "{"
            output += self.type_loop(row, u'{0}:{1},')

            output = output[0:-1] + "}" + "," + self.newline

        return output[:-2] + "];"

    # ASP / VBScript
    def asp(self, datagrid):
        self.syntax = PACKAGES + '/ASP/ASP.tmLanguage'
        #comment, comment_end = "'", ""
        output, r = u"", 0
        zipper = zip(range(len(self.headers)), self.headers, self.types)
        #print self.headers, self.types

        #begin render loop
        for row in datagrid:

            for c, key, item_type in zipper:

                if item_type == str:
                    row[key] = '"' + (row[key] or "") + '"'
                if item_type is None:
                    row[key] = 'null'

                output += u'myArray({0},{1}) = {2}'.format(c, r, row[key] + self.newline)
            r = r + 1

        dim = u'Dim myArray({0},{1}){2}'.format(c, r - 1, self.newline)

        return dim + output

    def tr(self, row):
        """Helper for HTML converter"""
        return "{i}{i}<tr>{n}" + row + "{i}{i}</tr>{n}"

    def html(self, datagrid):
        """HTML Table converter"""
        self.syntax = PACKAGES + '/HTML/HTML.tmLanguage'
        thead, tbody = u"", u""

        # Render table head
        for header in self.headers:
            thead += u'{i}{i}{i}<th>' + header + '</th>{n}'

        thead = self.tr(thead)

        # Render table rows
        for row in datagrid:
            rowText = u""

            # Sadly, dictReader doesn't always preserve row order,
            # so we loop through the headers instead.
            for key in self.headers:
                rowText += u'{i}{i}{i}<td>' + (row[key] or "") + u'</td>{n}'

            tbody += self.tr(rowText)

        table = u"<table>{n}{i}<thead>{n}" + thead + u"</thead>{n}"
        table += u"{i}<tbody>{n}" + tbody + u"</tbody>{n}</table>"

        if self.html_utf8:
            return table.format(i=self.indent, n=self.newline)
        else:
            return table.format(i=self.indent, n=self.newline).encode('ascii', 'xmlcharrefreplace')

    def javascript(self, datagrid):
        """JavaScript object converter"""
        self.syntax = PACKAGES + '/JavaScript/JavaScript.tmLanguage'
        output = u'var dataConverter = [' + self.newline

        #begin render loop
        for row in datagrid:
            output += self.indent + "{" + self.type_loop(row, u'{0}: {1}, ')
            output = output[:-2] + "}," + self.newline

        return output[:-2] + self.newline + '];'

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

        table = u'DataConverter'

        # CREATE TABLE statement
        create = u'CREATE TABLE ' + table + '({n}'
        create += self.indent + u"id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,{n}"

        # INSERT TABLE Statement
        insert = u'INSERT INTO ' + table + " {n}{i}("

        # VALUES list
        values = u"VALUES" + self.newline

        # Loop through headers
        for header, typ in zip(self.headers, self.types):
            if typ == str:
                typ = u'VARCHAR(255)'
            elif typ == float:
                typ = u'FLOAT'
            elif typ == int:
                typ = u'INT'

            insert += header + ","

            create += u'{i}' + header + " " + typ + "," + self.newline

        create = create[:-2] + '{n}'  # Remove the comma and newline
        create += u');{n}'

        insert = insert[:-1] + u") {n}"

        # loop through rows
        for row in datagrid:
            values += self.indent + u"("
            values += self.type_loop(row, form=u'{1},', nulltxt='NULL')

            values = values[:-1] + u'),' + self.newline

        output = create + insert + values[:-2] + ';'
        return output.format(i=self.indent, n=self.newline)

    def php(self, datagrid):
        """PHP converter"""
        self.syntax = PACKAGES + '/PHP/PHP.tmLanguage'
        #comment, comment_end = "//", ""
        output = u"$DataConverter = array(" + self.newline

        #begin render loop
        for row in datagrid:
            output += self.indent + u"array("
            output += self.type_loop(row, u'"{0}"=>{1}, ')

            output = output[:-2] + u")," + self.newline

        return output[:-1] + self.newline + u");"

    def python_dict(self, datagrid):
        """Python dict converter"""
        self.syntax = PACKAGES + '/Python/Python.tmLanguage'
        fields = []
        for row in datagrid:
            outrow = {}
            for k, t in zip(self.headers, self.types):
                if t == int:
                    outrow[k] = int(row[k])
                elif t == float:
                    outrow[k] = float(row[k])
                else:
                    outrow[k] = row[k]
            fields.append(outrow)

        return repr(fields)

    def python_list(self, datagrid):
        """Python list of lists converter"""
        self.syntax = PACKAGES + '/Python/Python.tmLanguage'
        fields = []
        for row in datagrid:
            outrow = []
            for k, t in zip(self.headers, self.types):
                if t == int:
                    outrow.append(int(row[k]))
                elif t == float:
                    outrow.append(float(row[k]))
                else:
                    outrow.append(row[k])
            fields.append(outrow)
        return '# headers = ' + repr(self.headers) + self.newline + repr(fields)

    def ruby(self, datagrid):
        """Ruby converter"""
        self.syntax = PACKAGES + '/Ruby/Ruby.tmLanguage'
        #comment, comment_end = "#", ""
        output = u"["

        #begin render loop
        for row in datagrid:
            output += "{"
            output += self.type_loop(row, u'"{0}"=>{1}, ', nulltxt='nil')

            output = output[:-2] + "}," + self.newline

        return output[:-2] + "];"

    def xml(self, datagrid):
        """XML Nodes converter"""
        self.syntax = PACKAGES + '/XML/XML.tmLanguage'
        output_text = u'<?xml version="1.0" encoding="UTF-8"?>{n}<rows>{n}'

        #begin render loop
        for row in datagrid:
            output_text += u'{i}<row>{n}'
            for header in self.headers:
                item = row[header] or ""
                output_text += u'{i}{i}<{1}>{0}</{1}>{n}'.format(item, header, i=self.indent, n=self.newline)

            output_text += u"{i}</row>{n}"

        output_text += u"</rows>"

        return output_text.format(i=self.indent, n=self.newline).encode('ascii', 'xmlcharrefreplace')

    def xmlProperties(self, datagrid):
        """XML properties converter"""
        self.syntax = PACKAGES + '/XML/XML.tmLanguage'
        output_text = u'<?xml version="1.0" encoding="UTF-8"?>{n}<rows>{n}'

        #begin render loop
        for row in datagrid:
            row_list = []

            for header in self.headers:
                item = row[header] or ""
                row_list.append(u'{0}="{1}"'.format(header, item))
                row_text = u" ".join(row_list)

            output_text += u"{i}<row " + row_text + "></row>{n}"

        output_text += u"</rows>"

        return output_text.format(i=self.indent, n=self.newline).encode('ascii', 'xmlcharrefreplace')

    def text_table(self, datagrid):
        """text table converter"""
        self.syntax = PACKAGES + '/Text/Plain text.tmLanguage'
        output_text, divline, field_length, _datagrid = u'|', u'+', {}, []

        _datagrid = [row for row in datagrid]

        for header in self.headers:
            length = len(header) + 1  # Add 1 to account for end-padding

            for row in _datagrid:
                try:
                    length = max(length, len(row[header]) + 1)
                except:
                    pass
            field_length[header] = length
            divline += '-' * (field_length[header] + 1) + '+'
            output_text += ' ' + header + ' ' * (field_length[header] - len(header)) + '|'

        divline += u'{n}'
        output_text = u'{0}{1}{{n}}{0}'.format(divline, output_text)

        #begin render loop
        for row in _datagrid:
            row_text = u'|'

            for header in self.headers:
                item = row[header] or ""
                row_text += u' ' + item + ' ' * (field_length[header] - len(item)) + '|'

            output_text += row_text + "{n}"

        output_text += divline
        return output_text.format(n=self.newline)
